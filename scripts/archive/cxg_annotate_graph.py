import asyncio
import os.path
import json
import pandas as pd

from dotenv import load_dotenv
from pydantic_graph import BaseNode, End, Graph, GraphRunContext

from amica.agents.annotator.annotator_agent import annotator_agent
from amica.agents.paper_celltype.paper_celltype_agent import (
    celltype_agent,
    CellTypeEntry,
)
from amica.agents.annotator.annotator_agent import TextAnnotation
from amica.utils.pubmed_utils import get_doi_text

from dataclasses import dataclass
import logfire
import logging

cxg_annotate_logger = logging.getLogger(__name__)
cxg_annotate_logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console.setFormatter(formatter)
cxg_annotate_logger.addHandler(console)

cxg_annotate_logger.propagate = True
logfire.configure()

ANNOTATIONS_BATCH_SIZE = 5

IS_TEST_MODE = False
TEST_ANNOTATIONS_COUNT = 4  # Number of annotations to process in test mode

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(CURRENT_DIR, "resources")
PUBLICATIONS_DIR = os.path.join(RESOURCES_DIR, "publications")
EXPANSIONS_DIR = os.path.join(RESOURCES_DIR, "expansions")
INPUT_DIR = os.path.join(RESOURCES_DIR, "input")  # Directory containing input TSV files
OUTPUT_DIR = os.path.join(
    RESOURCES_DIR, "output"
)  # Directory for output folders per dataset


@dataclass
class Dataset:
    name: str
    publication_file_name: str
    supplementary_file_name: str
    data_file_name: str


@dataclass
class State:
    articles: set[str]
    annotations: list[dict]
    article_to_annotations: dict[str, dict]
    paper_expansion: dict[str, CellTypeEntry]
    dataset_names: list[str]  # Track which datasets were processed
    is_test_mode: bool = IS_TEST_MODE


@dataclass
class GetGroundings(BaseNode[State, None, str]):

    async def run(self, ctx: GraphRunContext[State]) -> End:
        annotations = ctx.state.annotations
        cxg_annotate_logger.info(f"Total annotations to process: {len(annotations)}")

        for annotation in annotations:
            if "enrichment" not in annotation:
                annotation["enrichment"] = CellTypeEntry(
                    name=annotation["annotation_text"],
                    full_name="",
                    paper_synonyms="",
                    tissue_context="",
                )
                print(
                    f"Warning: No enrichment found for annotation '{annotation['annotation_text']}', using blank entry."
                )
            # delete tissue_context of all enrichments
            annotation["enrichment"].tissue_context = ""
            # reset previous grounding results so reruns don't mix states
            annotation["grounding_cl_id"] = None
            annotation["grounding_cl_label"] = None

        # Sort annotations by article_id_doi, then annotation_text
        annotations.sort(
            key=lambda annot: (
                annot.get("article_id_doi") or "",
                annot.get("annotation_text") or "",
            )
        )

        base_cache_dir = os.path.join(RESOURCES_DIR, "cache")
        os.makedirs(base_cache_dir, exist_ok=True)

        batch_size = 4
        all_groundings = []

        annotations_by_dataset: dict[str, list[dict]] = {}
        for annotation in annotations:
            dataset_name = annotation.get("dataset_name", "unknown_dataset")
            annotations_by_dataset.setdefault(dataset_name, []).append(annotation)

        for dataset_name in ctx.state.dataset_names:
            dataset_annotations = annotations_by_dataset.get(dataset_name, [])
            if not dataset_annotations:
                continue

            dataset_cache_dir = os.path.join(
                base_cache_dir,
                normalise_file_name(dataset_name),
            )
            os.makedirs(dataset_cache_dir, exist_ok=True)

            for batch_index, batch_start in enumerate(
                range(0, len(dataset_annotations), batch_size)
            ):
                batch = dataset_annotations[batch_start : batch_start + batch_size]
                expected_inputs = [
                    annotation.get("annotation_text", "") or "" for annotation in batch
                ]
                batch_cache_path = os.path.join(
                    dataset_cache_dir, f"batch_{batch_index}.json"
                )

                batch_groundings: list[TextAnnotation]
                cache_hit = False
                if os.path.exists(batch_cache_path):
                    with open(batch_cache_path, "r") as f:
                        cached_payload = json.load(f)
                    if isinstance(cached_payload, list):
                        cached_inputs = [
                            entry.get("input_name", "") for entry in cached_payload
                        ]
                        if cached_inputs == expected_inputs:
                            batch_groundings = [
                                TextAnnotation(**entry) for entry in cached_payload
                            ]
                            cache_hit = True

                if not cache_hit:
                    print(
                        "Processing batch: ",
                        batch_index + 1,
                        " of ",
                        (len(dataset_annotations) + batch_size - 1) // batch_size,
                    )
                    expansions_json = json.dumps(
                        [annotation["enrichment"].model_dump() for annotation in batch],
                        indent=2,
                    )
                    agent_response = await annotator_agent.run(expansions_json)
                    batch_groundings = agent_response.output.annotations
                    with open(batch_cache_path, "w") as f:
                        json.dump(
                            [entry.model_dump() for entry in batch_groundings],
                            f,
                            indent=2,
                        )

                all_groundings.extend(batch_groundings)
                # update batch annotations with grounding results
                for annotation in batch:
                    # convert enrichment to json to make df mode readable
                    annotation["enrichment"] = annotation["enrichment"].model_dump()
                    related_groundings = [
                        gr
                        for gr in batch_groundings
                        if gr.input_name == annotation["annotation_text"]
                    ]
                    if related_groundings:
                        valid_grounding = next(
                            (
                                g
                                for g in related_groundings
                                if "NO MATCH" not in g.cl_id
                            ),
                            None,
                        )
                        if valid_grounding:
                            grounding_to_use = valid_grounding
                        else:
                            grounding_to_use = related_groundings[0]
                        annotation["grounding_cl_id"] = grounding_to_use.cl_id
                        annotation["grounding_cl_label"] = grounding_to_use.cl_label

        # Create output directory
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # Save per-dataset results in separate folders
        for dataset_name in ctx.state.dataset_names:
            dataset_output_dir = os.path.join(OUTPUT_DIR, dataset_name)
            os.makedirs(dataset_output_dir, exist_ok=True)

            dataset_annotations = [
                ann for ann in annotations if ann.get("dataset_name") == dataset_name
            ]
            if dataset_annotations:
                # Save all annotations for this dataset
                df_dataset_all = pd.DataFrame(dataset_annotations)
                all_annotations_file = os.path.join(
                    dataset_output_dir, "cell_type_annotations_un_filtered.tsv"
                )
                df_dataset_all.to_csv(all_annotations_file, sep="\t", index=False)

                # Save filtered groundings
                df_dataset_filtered = df_dataset_all[
                    df_dataset_all["grounding_cl_id"].notna()
                ]
                if not df_dataset_filtered.empty:
                    df_dataset_filtered["result"] = (
                        df_dataset_filtered["cl_id"]
                        .eq(df_dataset_filtered["grounding_cl_id"])
                        .map({True: "TRUE", False: "FALSE"})
                    )
                    groundings_file = os.path.join(dataset_output_dir, "groundings.tsv")
                    df_dataset_filtered.to_csv(groundings_file, sep="\t", index=False)
                    cxg_annotate_logger.info(
                        f"Saved results for dataset: {dataset_name} to {dataset_output_dir}"
                    )

        return End("Report generated and saved to individual dataset folders.")


@dataclass
class GetFullNames(BaseNode[State, None, str]):

    async def run(self, ctx: GraphRunContext[State]) -> GetGroundings:
        print("Running GetFullNames node")
        if not os.path.exists(EXPANSIONS_DIR):
            os.makedirs(EXPANSIONS_DIR)
        article_to_annotations = ctx.state.article_to_annotations
        annotations_by_dataset_and_article: dict[str, dict[str, list[dict]]] = {}
        for article_pmc, article_annotations in article_to_annotations.items():
            for annotation in article_annotations:
                dataset_name = annotation.get("dataset_name", "unknown_dataset")
                dataset_articles = annotations_by_dataset_and_article.setdefault(
                    dataset_name, {}
                )
                dataset_articles.setdefault(article_pmc, []).append(annotation)

        for dataset_name in ctx.state.dataset_names:
            dataset_articles = annotations_by_dataset_and_article.get(dataset_name, {})
            if not dataset_articles:
                continue

            dataset_cache_dir = os.path.join(
                EXPANSIONS_DIR, normalise_file_name(dataset_name)
            )
            os.makedirs(dataset_cache_dir, exist_ok=True)

            articles = sorted(
                str(a) if a is not None else "" for a in dataset_articles.keys()
            )
            index = 1
            for article_pmc in articles:
                print(
                    f"[{dataset_name}] Processing article: {article_pmc}  -  {index}/{len(articles)}"
                )
                index += 1
                article_annotations = dataset_articles[article_pmc]

                for batch_index in range(
                    0, len(article_annotations), ANNOTATIONS_BATCH_SIZE
                ):
                    batch = article_annotations[
                        batch_index : batch_index + ANNOTATIONS_BATCH_SIZE
                    ]
                    dataset_cache = os.path.join(
                        dataset_cache_dir,
                        f"{normalise_file_name(article_pmc)}_batch_{batch_index // ANNOTATIONS_BATCH_SIZE}.json",
                    )
                    cc_labels = [{"cc.label": ann["annotation_text"]} for ann in batch]

                    if not os.path.exists(dataset_cache):
                        full_text_path = os.path.join(
                            PUBLICATIONS_DIR, f"{normalise_file_name(article_pmc)}.txt"
                        )
                        if os.path.exists(full_text_path):
                            with open(full_text_path, "r", encoding="utf-8") as f:
                                paper_full_text = f.read()

                            prompt_instructions = f"""
                            You are tasked with extracting cell type information from the provided academic paper content,
                            and the provided JSON data.
        
                            The JSON contains cell type annotations (cc.label column) from single-cell transcriptomic data.
        
                            Based on the following JSON data and academic paper content, generate a list of structured
                            cell type entries. Each entry must follow the `CellTypeEntry` schema.
        
                            --- JSON List Input Data:
                            {json.dumps(cc_labels, indent=2)}
        
                            --- Academic Paper Content (extracted from PDF):
                            {paper_full_text}
        
                            --- COLUMN DEFINITIONS AND LOGIC:
                            - `name`: The exact `cc.label` from the input JSON.
                            - `full_name`: Use the following logic:
                                1. If the full label (e.g., "SI_TA") is defined directly in the paper, use the exact definition.
                                2. If not, check if individual parts (e.g., prefixes, suffixes) are defined and reconstruct/assemble the `full_name` from the parts found (e.g., for "SI_TA", assemble "small intestine transit amplifying cell" if paper defines "SI" as "small intestine" and "TA" as "transit amplifying cell").
                                3. If the label begins with a defined prefix abbreviation (e.g., "RGC"), expand the prefix and append the remaining label (e.g., "RGC10" becomes "retinal ganglion cell 10").
                                4. If only one part is defined, use just that part.
                                5. If no parts are defined, leave this field blank.
                            - `paper_synonyms`: Use only synonyms mentioned in the paper using:
                                - Abbreviation lists
                                - Abbreviation definitions (e.g., "follicle-associated epithelium (FAE)")
                                - Patterns like “also known as”, “termed”, “referred to as”
                                - Include all found; separate with semicolons (;)
                            - `tissue_context`: Exact quoted tissue(s) or anatomical terms from the paper where the cell type was identified.
        
                            Process all `cc.label` entries from the JSON data automatically.
                            Do not ask for confirmation.
                            Provide the output as a JSON array of `CellTypeEntry` objects.
                            """
                            agent_response = await celltype_agent.run(
                                prompt_instructions
                            )

                            for entry in agent_response.output.cell_type_annotations:
                                entry_copy = entry.model_copy()
                                print(
                                    f"Name: {entry.name}, Full Name: {entry.full_name}, Synonyms: {entry.paper_synonyms}, Tissue Context: {entry.tissue_context}"
                                )
                                # add entry to the related article_annotations
                                for ann in article_annotations:
                                    if ann["annotation_text"] == entry.name:
                                        ann["enrichment"] = entry_copy.model_copy()

                            expansions = agent_response.output.cell_type_annotations
                            print(
                                f"Saving results to cache for dataset {dataset_name}, article: {article_pmc}"
                            )
                            with open(dataset_cache, "w") as cache_file:
                                json.dump(
                                    [entry.model_dump() for entry in expansions],
                                    cache_file,
                                    indent=2,
                                )
                        else:
                            print(
                                f"Error: Full text file not found for article for name expansion: {article_pmc}"
                            )
                    else:
                        print(
                            f"[{dataset_name}] Using cached data for article: {article_pmc}"
                        )
                        with open(dataset_cache, "r") as cache_file:
                            cached_data = json.load(cache_file)
                            for cached_entry in cached_data:
                                cached_model = CellTypeEntry(**cached_entry)
                                for ann in article_annotations:
                                    if ann["annotation_text"] == cached_model.name:
                                        ann["enrichment"] = cached_model.model_copy()
                                        print(
                                            "Using cached enrichment data for annotation:",
                                            ann["annotation_text"],
                                        )
        return GetGroundings()


@dataclass
class PrepareData(BaseNode[State, None, str]):

    async def run(self, ctx: GraphRunContext[State]) -> GetFullNames:
        print("Running PrepareData node")
        annotations, article_to_annotations, dataset_names = load_cxg_annotations()

        if ctx.state.is_test_mode:
            # only process a few annotations in test mode
            annotations = list(annotations)[:TEST_ANNOTATIONS_COUNT]
            # filter article_to_annotations to only include those in annotations
            article_to_annotations = {
                k: v
                for k, v in article_to_annotations.items()
                if k in {ann["article_id_doi"] for ann in annotations}
            }

        unique_dois = set(article_to_annotations.keys())
        print(f"Unique DOISs to download: {len(unique_dois)}")
        articles = download_publication_texts(unique_dois)
        print(f"Downloaded articles: {len(articles)}")

        ctx.state.articles = articles
        ctx.state.annotations = annotations
        ctx.state.article_to_annotations = article_to_annotations
        ctx.state.dataset_names = dataset_names

        return GetFullNames()


def load_cxg_annotations():
    """
    Load annotations from all TSV files in the INPUT_DIR.
    Returns: (annotations, article_to_annotations, dataset_names)
    """
    if not os.path.exists(INPUT_DIR):
        # Fallback to old hardcoded path for backward compatibility
        cxg_annotate_logger.warning(
            f"Input directory not found: {INPUT_DIR}. Using legacy single file."
        )
        tsv_path = os.path.join(
            os.getcwd(),
            "resources",
            "ac8619d0-4fff-4296-913a-819d1e361ba0_cxg_dataset_unique.tsv",
        )
        if not os.path.exists(tsv_path):
            raise FileNotFoundError(
                f"Neither input directory nor legacy file found. Please create {INPUT_DIR} with TSV files."
            )
        tsv_files = [tsv_path]
    else:
        # Find all TSV files in INPUT_DIR
        tsv_files = [
            os.path.join(INPUT_DIR, f)
            for f in os.listdir(INPUT_DIR)
            if f.endswith(".tsv") or f.endswith(".TSV")
        ]

        if not tsv_files:
            raise FileNotFoundError(f"No TSV files found in {INPUT_DIR}")

    cxg_annotate_logger.info(f"Found {len(tsv_files)} TSV file(s) to process")

    annotations = []
    article_to_annotations = {}
    dataset_names = []

    for tsv_path in tsv_files:
        dataset_name = os.path.splitext(os.path.basename(tsv_path))[0]
        dataset_names.append(dataset_name)
        cxg_annotate_logger.info(f"Loading dataset: {dataset_name}")

        df = pd.read_csv(tsv_path, sep="\t")

        for _, row in df.iterrows():
            if pd.isna(row["reference"]):
                continue
            paper_doi = str(row["reference"]).replace("https://doi.org/", "DOI:")
            annotation = {
                "annotation_text": row["author_cell_type"],
                "cl_id": row["CL_ID"],
                "cl_label": row["CL_label"],
                "article_id_doi": paper_doi,
                "dataset_name": dataset_name,  # Track which dataset this came from
            }
            annotations.append(annotation)
            article_to_annotations.setdefault(paper_doi, []).append(annotation)

    cxg_annotate_logger.info(
        f"Loaded {len(annotations)} total annotations from {len(dataset_names)} dataset(s)"
    )
    return annotations, article_to_annotations, dataset_names


def download_publication_texts(dois, publications_dir=PUBLICATIONS_DIR):
    """
    Download full text for each DOI using get_doi_text and save to publications_dir/pmc_id.txt.
    Skips download if file already exists. Creates publications_dir if needed.
    Args:
        dois (Iterable[str]): Set or list of PMC IDs.
        publications_dir (str): Directory to save text files.
    """
    if not os.path.exists(publications_dir):
        os.makedirs(publications_dir)
    articles = set()
    for doi in dois:
        if doi:
            file_path = os.path.join(
                publications_dir, f"{normalise_file_name(doi)}.txt"
            )
            if os.path.exists(file_path):
                articles.add(doi)
                continue
            text = get_doi_text(doi)
            if text:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                articles.add(doi)
            else:
                print(f"Error: No full-text found for ID {doi}")
    return articles


def normalise_file_name(doi: str) -> str:
    return doi.replace("/", "_").replace(":", "_").replace(".", "_")


async def main():
    state = State(set(), list(), dict(), dict(), list(), is_test_mode=IS_TEST_MODE)
    validation_graph = Graph(nodes=(PrepareData, GetFullNames, GetGroundings))
    result = await validation_graph.run(PrepareData(), state=state)
    print(result.output)
    # print(validation_graph.mermaid_code())


if __name__ == "__main__":
    load_dotenv()
    print(os.environ.get("OPENAI_API_KEY"))
    asyncio.run(main())
