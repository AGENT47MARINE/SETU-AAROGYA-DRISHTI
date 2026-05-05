from services.nlp.entity_extractor import EntityExtractor

def test():
    print("Testing NER extraction...")
    extractor = EntityExtractor() # Uses default d4data/biomedical-ner-all
    res = extractor.extract("I have a fever and took paracetamol.")
    print(f"Results: {res}")

if __name__ == "__main__":
    test()
