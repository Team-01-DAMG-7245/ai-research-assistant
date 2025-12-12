# Project Disclosures

## Work Disclosure

### Attestation and Contribution Declaration

**WE ATTEST THAT WE HAVEN'T USED ANY OTHER STUDENTS' WORK IN OUR ASSIGNMENT AND ABIDE BY THE POLICIES LISTED IN THE STUDENT HANDBOOK.**

### Team Member Contributions

- **Member 1**: 33.3%
- **Member 2**: 33.3%
- **Member 3**: 33.3%

All team members contributed equally to the development, testing, and documentation of this project. Each member was responsible for different components of the system, and all work was completed collaboratively with full transparency and shared understanding of the codebase.

---

## AI Usage Disclosure

This project extensively uses AI tools as part of its core functionality and development process. Below is a comprehensive disclosure of AI tools used and their purposes.

### AI Tools Used in Project Development

#### 1. **Cursor AI**
- **Purpose**: debugging assistance
- **Usage Areas**:
  - Error handling and exception management
  - Code refactoring and optimization suggestions
  - Documentation generation

#### 2. **OpenAI GPT-4o Mini** (Core Functionality)
- **Purpose**: This is a **core component** of the application, not just a development tool
- **Usage Areas**:
  - **Search Agent**: Query expansion (generating 3-5 diverse search queries from user input)
  - **Synthesis Agent**: Research report generation (1200-1500 word reports with citations)
  - **Validation Agent**: Quality analysis and citation verification
- **Extent**: Essential runtime component - the system cannot function without it
- **Location**: `src/utils/openai_client.py`, `src/agents/search_agent.py`, `src/agents/synthesis_agent.py`, `src/agents/validation_agent.py`

#### 3. **OpenAI Text Embeddings (text-embedding-3-small)**
- **Purpose**: Core functionality for semantic search
- **Usage Areas**:
  - Converting user queries to vector embeddings
  - Converting document chunks to embeddings during data ingestion
  - Enabling semantic search in Pinecone vector database
- **Extent**: Essential runtime component for RAG (Retrieval-Augmented Generation)
- **Location**: `src/utils/pinecone_rag.py`, `src/pipelines/ingestion.py`
