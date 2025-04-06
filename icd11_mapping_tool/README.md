# 🗺️ Mapping Journey: ICD-11 to CIEL Concepts

## Introduction

This project documents the efforts to map **27,796 CIEL diagnosis concepts** to **ICD-11**.  
Mapping to SNOMED CT and ICD-10 was previously easier due to curated datasets. However, ICD-11 introduced challenges because of its newer structure, use of extension codes, and complexity.  
Manual mapping was extremely time-consuming, potentially taking around 193 days.  
Thus, automated tools and strategies were developed to accelerate the process.

## Phase 1: Leveraging Existing Resources and Developing Support Tools

The **OCL Mapping Tool** was utilized to generate initial suggestions, producing ~1,693 ICD-11 mappings. However, it assumed a *SAME-AS* relation by default, so manual curation was still necessary.

**CIEL Lab**, a custom web service, was used to curate mappings, allowing users to:
- Correct suggested ICD-11 codes
- Provide missing codes
- Define mapping types (SAME-AS, NARROWER-THAN, BROADER-THAN)

Each ICD-11 suggestion is supported by:
- Linearization search (ICD API)
- Autocode search (ICD API)
- WHO ICD-10 to ICD-11 cross-reference mapping

These auxiliary searches help automate the curation process.

## Phase 2: Semantic Approach

A semantic vectorization plan was proposed to complement traditional mapping strategies, leveraging:
- **ChromaDB** for semantic search
- Vectorized datasets: CIEL concepts, ICD-10, ICD-11 FSNs, synonyms, and index terms

This phase aims to improve matching suggestions through meaning-based retrieval instead of plain text search.

## Phase 3: Working with Extensions

Extensions in ICD-11 (codes starting with `X`) are used for further specifying clinical concepts, such as location or severity.  
The project outlines:
- The importance of managing stem codes and extension codes.
- Future plans to post-coordinate terms automatically.
- A structured pipeline to prepare data, vectorize, query, and validate extension usage.

---

# ✅ Testing and Results

Once the environment is set up:
- **Jupyter Notebook** can query the local MySQL database.
- **ICD-11 API** can perform linearization and autocode searches.
- **WHO Cross-Reference** lookups assist in suggesting ICD-11 mappings.
- **Quality Assurance** scripts check if proposed ICD-11 codes are terminal (leaf nodes) or have valid extensions.

Example successful match:
- `Carrion's disease` (CIEL) ➔ `ICD-11 1C11.0 - Carrion disease`

---

# 🧩 Future Work

- Full integration of semantic search inside OCL.
- Enhancing the extension code handling and smart post-coordination.