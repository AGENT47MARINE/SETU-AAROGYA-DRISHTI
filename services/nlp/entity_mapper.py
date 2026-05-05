from thefuzz import process

class EntityMapper:
    """
    Maps extracted entities to medical ontologies (SNOMED-CT/ICD-10).
    Uses fuzzy matching against a curated local map for Phase 1.
    """
    def __init__(self):
        # Sample ontology map (expandable)
        self.ontology_map = {
            "fever": {"code": "386661006", "system": "SNOMED-CT"},
            "cough": {"code": "49727002", "system": "SNOMED-CT"},
            "kidney failure": {"code": "236423003", "system": "SNOMED-CT"},
            "dizziness": {"code": "404640003", "system": "SNOMED-CT"},
            "paracetamol": {"code": "387517004", "system": "SNOMED-CT"},
            "diethylene glycol": {"code": "10022002", "system": "SNOMED-CT"}
        }

    def map_to_ontology(self, entity_text: str, threshold=80):
        """
        Returns (code, system) if a match is found above threshold.
        """
        text = entity_text.lower().strip()
        choices = list(self.ontology_map.keys())
        
        match, score = process.extractOne(text, choices)
        
        if score >= threshold:
            return self.ontology_map[match]
        
        return {"code": "UNKNOWN", "system": "LOCAL"}

if __name__ == "__main__":
    mapper = EntityMapper()
    test_entities = ["feverish", "kidney issues", "crocin"]
    for ent in test_entities:
        mapping = mapper.map_to_ontology(ent)
        print(f"Text: {ent} -> Code: {mapping['code']} ({mapping['system']})")
