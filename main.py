import os
import re
import openai
from flask import Flask, jsonify, request, send_file
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure the OpenAI library
openai.api_key = os.environ["OPENAI_API_KEY"]

app = Flask(__name__)

# --- Dictionnaire des Prompts pour chaque type de cartographie ---
PROMPT_INSTRUCTIONS = {
    "organisationnelle_flux": {
        "type": "mermaid",
        "expert_role": "un architecte organisationnel",
        "instructions": """1. Générez un diagramme de relations `graph TD`. 2. Définissez chaque département/rôle comme un nœud. 3. Montrez les relations (supervision, collaboration) avec des flèches étiquetées. Ex: `Direction -- \"Supervise\" --> Ventes`."""
    },
    "organisationnelle_mental": {
        "type": "markmap",
        "expert_role": "un expert en conseil organisationnel",
        "instructions": """1. La racine est l'entreprise. 2. Créez des branches (##) pour les départements. 3. Sous-branches (###) pour les rôles. 4. Puces pour les responsabilités."""
    },
    "processus_flux": {
        "type": "mermaid",
        "expert_role": "un analyste expert en modélisation de processus métier (BPMN)",
        "instructions": """1. Générez un diagramme de flux `graph TD`. 2. Le départ est l'objectif `A[Objectif: {description}]`. 3. Enchaînez les étapes clés avec `-->`. 4. Utilisez des losanges `{{Question?}}` pour les décisions et des flèches étiquetées ` -- Oui --> `."""
    },
    "processus_mental": {
        "type": "markmap",
        "expert_role": "un analyste expert en processus métier",
        "instructions": """1. La racine est l'entreprise. 2. Créez 3 branches (##): Pilotage, Réalisation, Support. 3. Sous-branches (###) pour les processus spécifiques. 4. Puces pour les activités clés."""
    },
    "applicative_flux": {
        "type": "mermaid",
        "expert_role": "un architecte de systèmes d'information (SI)",
        "instructions": """1. Générez un diagramme de flux `graph TD`. 2. Chaque application est un nœud. 3. Montrez les flux de données ou appels API avec des flèches étiquetées. Ex: `CRM -- \"Synchro clients\" --> ERP`."""
    },
    "applicative_mental": {
        "type": "markmap",
        "expert_role": "un architecte de systèmes d'information (SI)",
        "instructions": """1. La racine est l'entreprise. 2. Créez des branches (##) pour les catégories fonctionnelles. 3. Listez les applications (###) sous chaque catégorie. 4. Puces pour les fonctions clés."""
    },
    "donnees_flux": {
        "type": "mermaid",
        "expert_role": "un architecte de données",
        "instructions": """1. Générez un diagramme de flux de données `graph TD`. 2. Les entités ou bases de données sont des nœuds. 3. Montrez le mouvement des données avec des flèches étiquetées. Ex: `SystemeA -- \"Mise à jour\" --> BDD_Clients`."""
    },
    "donnees_mental": {
        "type": "markmap",
        "expert_role": "un architecte de données",
        "instructions": """1. La racine est l'entreprise. 2. Créez des branches (##) pour les domaines de données. 3. Sous-branches (###) pour les entités. 4. Puces pour les attributs importants."""
    },
    "risques_flux": {
        "type": "mermaid",
        "expert_role": "un gestionnaire de risques",
        "instructions": """1. Générez un diagramme de causalité `graph TD`. 2. Le risque est un nœud central. 3. Montrez les causes et les conséquences avec des flèches étiquetées. Ex: `Cause -- \"Provoque\" --> Risque -- \"Entraîne\" --> Impact`."""
    },
    "risques_mental": {
        "type": "markmap",
        "expert_role": "un gestionnaire de risques",
        "instructions": """1. La racine est l'entreprise. 2. Créez des branches (##) pour les catégories de risques. 3. Identifiez des risques spécifiques (###). 4. Puces pour les mesures de contrôle."""
    }
}

@app.route("/")
def index():
    return send_file('src/index.html')

@app.route("/generate", methods=["POST"])
def generate():
    try:
        description = request.form.get("description")
        map_type = request.form.get("map_type", "processus_flux")

        if not description:
            return jsonify({"error": "La description est requise"}), 400
        if map_type not in PROMPT_INSTRUCTIONS:
            return jsonify({"error": "Type de carte invalide"}), 400

        config = PROMPT_INSTRUCTIONS[map_type]
        expert_role = config["expert_role"]
        instructions = config["instructions"].format(description=description)
        output_type = config["type"]

        if output_type == 'mermaid':
            system_prompt = "Vous êtes un assistant qui génère des diagrammes au format Mermaid."
            final_prompt = f"""En tant que {expert_role}, créez un diagramme Mermaid pour: "{description}".\n\nInstructions:\n{instructions}\n\nRÈGLE CRITIQUE: Votre réponse doit être UNIQUEMENT le code Mermaid dans un bloc ```mermaid. Ne rien inclure d'autre."""
        else: # markmap
            system_prompt = "Vous êtes un assistant qui génère des cartes mentales au format Markmap."
            final_prompt = f"""En tant que {expert_role}, créez une carte mentale Markmap pour: "{description}".\n\nInstructions:\n{instructions}\n\nRÈGLE CRITIQUE: Votre réponse doit être UNIQUEMENT le code markdown, commençant par un titre `#`."""

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": final_prompt}
            ]
        )

        raw_data = response.choices[0].message.content
        cleaned_data = clean_response(raw_data, output_type)
        
        if not cleaned_data:
            return jsonify({"error": "La réponse de l'IA était vide ou invalide. Veuillez réessayer."}), 500

        return jsonify({"map": cleaned_data, "type": output_type})

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": "Une erreur interne du serveur est survenue."}), 500

def clean_response(raw_text, response_type):
    cleaned_text = raw_text.strip()
    if response_type == 'mermaid':
        match = re.search(r"```(?:mermaid)?\n(.*?)\n```", cleaned_text, re.DOTALL)
        if match:
            return match.group(1).strip()
    else: # markmap
        cleaned_text = re.sub(r"```(?:markdown)?\n?", "", cleaned_text)
        cleaned_text = re.sub(r"\n?```", "", cleaned_text)
        lines = cleaned_text.strip().splitlines()
        first_md_line_index = next((i for i, line in enumerate(lines) if line.strip().startswith('#')), -1)
        if first_md_line_index != -1:
            return '\n'.join(lines[first_md_line_index:]).strip()
    return cleaned_text

def main():
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))

if __name__ == "__main__":
    main()
