import yara
import os

class NasoAnalyzer:
    def __init__(self, rules_path="shared/rules/"):
        self.rules_path = rules_path
        self.static_rules = self._load_static_rules(rules_path)
        self.dynamic_rules = {} # Rules from DB
        self.compiled_rules = self._compile_all()

    def _load_static_rules(self, rules_path):
        rule_files = {}
        if not os.path.exists(rules_path):
            rules_path = os.path.join(os.path.dirname(__file__), "..", "rules")
            
        if os.path.exists(rules_path):
            for filename in os.listdir(rules_path):
                if filename.endswith(".yar"):
                    rule_files[filename] = os.path.join(rules_path, filename)
        return rule_files

    def _compile_all(self):
        """Compila sia le regole statiche che quelle dinamiche."""
        # Aggiungiamo le statiche (filepaths)
        # Aggiungiamo le dinamiche (strings)
        # Nota: yara.compile supporta filepaths o source strings, ma mescolarli richiede attenzione.
        # Useremo 'sources' per tutto caricando i file statici in memoria se necessario, 
        # o useremo namespace diversi.
        
        sources = {}
        # Carica statiche come stringhe per coerenza
        for name, path in self.static_rules.items():
            try:
                with open(path, 'r') as f:
                    sources[f"static_{name}"] = f.read()
            except Exception as e:
                print(f"Error loading static rule {name}: {e}")

        # Aggiungi dinamiche
        for name, content in self.dynamic_rules.items():
            sources[f"dynamic_{name}"] = content
            
        if not sources:
            # Fallback rule per evitare crash se non ci sono regole
            sources["fallback"] = "rule fallback { condition: false }"
            
        return yara.compile(sources=sources)

    def refresh_dynamic_rules(self, db_rules):
        """Aggiorna le regole in memoria con quelle provenienti dal DB."""
        self.dynamic_rules = {r.name: r.content for r in db_rules}
        self.compiled_rules = self._compile_all()
        print(f"[NASO ANALYZER] Dynamic rules refreshed: {len(self.dynamic_rules)} rules loaded.")

    def analyze_text(self, text):
        """
        Analizza il testo e restituisce i match e lo score calcolato.
        """
        try:
            matches = self.compiled_rules.match(data=text)
        except Exception as e:
            print(f"YARA matching error: {e}")
            return [], 0
            
        results = []
        score = 0
        
        for match in matches:
            results.append({
                "rule": match.rule,
                "tags": match.tags,
                "meta": match.meta
            })
            # Logica di scoring: usa metadati YARA se presenti, altrimenti default
            rule_score = match.meta.get("score", 10)
            score += rule_score
            
        return results, min(score, 100)

analyzer = NasoAnalyzer()
