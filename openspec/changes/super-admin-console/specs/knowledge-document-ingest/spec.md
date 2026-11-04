# Spec Delta

## Purpose

让超级管理员上传条款文档并向量化，作为现有 RAG 检索的知识来源，同时查看文档目录和分块。

## ADDED Requirements

### Requirement: Super admin can upload a clause document
The system SHALL accept a pdf, docx, md, or txt file from a super admin, store the original file, and record a knowledge document with its title, optional product id, checksum, and processing status.

#### Scenario: Accepted file type
- **WHEN** a super admin uploads a non-empty pdf, docx, md, or txt file
- **THEN** the system stores the original and creates a knowledge-document record

#### Scenario: Rejected file type
- **WHEN** a super admin uploads a file whose type is not pdf, docx, md, or txt
- **THEN** the system rejects the upload and does not create vectors

### Requirement: Ingest writes vectors without rebuilding the collection
The system SHALL split and embed an accepted document into the existing `file_documents` collection, and SHALL NOT drop or recreate that collection.

#### Scenario: Successful ingest
- **WHEN** embedding and vector storage succeed for an uploaded document
- **THEN** the document status becomes available and its chunk count matches the stored vectors

#### Scenario: Ingest failure
- **WHEN** embedding or vector storage fails
- **THEN** the document status becomes failed and previously published vectors for that document remain unchanged

#### Scenario: Other documents stay in place
- **WHEN** one document is ingested
- **THEN** vectors belonging to other documents remain searchable

### Requirement: Replacing a document updates only its vectors
The system SHALL treat a new upload with the same document identity as a replacement, removing that document's previous vectors only after the new vectors are stored.

#### Scenario: Same document uploaded again
- **WHEN** a super admin uploads a new version of an existing knowledge document and the new write succeeds
- **THEN** retrieval uses the new chunks and the previous chunks for that document are gone

### Requirement: Super admin can inspect the knowledge base
The system SHALL list knowledge documents with status, title, optional product id, checksum, and chunk count, and SHALL return the text and metadata of chunks for one document.

#### Scenario: List documents
- **WHEN** a super admin requests the knowledge-document list
- **THEN** the system returns each stored document and its current status

#### Scenario: View chunks
- **WHEN** a super admin requests chunks for an available document
- **THEN** the system returns that document's stored chunk text and citation metadata

### Requirement: Retrieval can use newly ingested content
Knowledge retrieval SHALL be able to return chunks from a document whose status is available, including the document title, source, checksum, and product id when one was supplied.

#### Scenario: Query matches a new clause
- **WHEN** a knowledge query matches an available document ingested by the admin
- **THEN** the retrieval result can include that document's chunk and its citation metadata

### Requirement: Only a super admin can manage knowledge documents
The system SHALL reject knowledge upload, list, and chunk requests from callers who are not an enabled super admin.

#### Scenario: Unauthorized upload
- **WHEN** a caller without a super-admin session uploads a document
- **THEN** the system rejects the request and does not write vectors
