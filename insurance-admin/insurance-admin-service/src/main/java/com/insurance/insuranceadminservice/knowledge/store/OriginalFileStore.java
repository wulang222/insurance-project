package com.insurance.insuranceadminservice.knowledge.store;

public interface OriginalFileStore {

    String store(String filename, byte[] content);
}
