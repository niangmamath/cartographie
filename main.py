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
    "organisationnelle": {
        "expert_role": "un expert en conseil organisationnel",
        "instructions": """
        1. L'idée d'entreprise "{description}" doit être la racine centrale de la carte mentale (le titre principal #).
        2. Créez des branches principales (titres ##) pour les départements ou services clés (ex: Direction, Opérations, Commercial, Marketing, RH, Finance).
        3. Sous chaque branche principale, créez des sous-branches (titres ###) pour les rôles ou équipes spécifiques.
        4. Sous chaque sous-branche de rôle/équipe, générez 2 à 3 points concis (puces) décrivant leurs responsabilités principales.
        """
    },
    "processus": {
        "expert_role": "un analyste expert en processus métier",
        "instructions": """
        1. L'idée d'entreprise "{description}" doit être la racine centrale de la carte mentale (le titre principal #).
        2. Créez 3 branches principales (titres ##) pour les catégories de processus : Processus de Pilotage, Processus de Réalisation, et Processus de Support.
        3. Sous chaque branche principale, créez des sous-branches (titres ###) pour les processus spécifiques (ex: Ventes, Marketing, Facturation, Recrutement).
        4. Sous chaque sous-branche de processus, générez 2 à 4 points concis (puces) qui détaillent les activités ou étapes clés de ce processus.
        """
    },
    "applicative": {
        "expert_role": "un architecte de systèmes d'information (SI)",
        "instructions": """
        1. L'idée d'entreprise "{description}" doit être la racine centrale de la carte mentale (le titre principal #).
        2. Créez des branches principales (titres ##) pour les grandes catégories fonctionnelles (ex: Vente & Marketing, Opérations, Finance, Communication).
        3. Sous chaque branche, listez les types d'applications ou de systèmes qui seraient utilisés (titres ###), par exemple : CRM, ERP, Plateforme e-commerce, Outil d'analyse, Suite bureautique.
        4. Sous chaque application, générez 2 à 3 points (puces) décrivant ses fonctions clés ou les données qu'elle gère.
        """
    },
    "donnees": {
        "expert_role": "un architecte de données",
        "instructions": """
        1. L'idée d'entreprise "{description}" doit être la racine centrale de la carte mentale (le titre principal #).
        2. Créez des branches principales (titres ##) représentant les principaux domaines de données (ex: Données Clients, Données Produits, Données Financières, Données Opérationnelles).
        3. Pour chaque domaine, créez des sous-branches (titres ###) pour les flux de données majeurs ou les points d'échange.
        4. Pour chaque flux, utilisez des puces pour décrire : l'origine de la donnée, sa destination (quelle application ou service), et sa nature (ex: "Info commande du site web vers le CRM").
        """
    },
    "risques": {
        "expert_role": "un gestionnaire de risques (risk manager)",
        "instructions": """
        1. L'idée d'entreprise "{description}" doit être la racine centrale de la carte mentale (le titre principal #).
        2. Créez des branches principales (titres ##) pour les catégories de risques : Risques Opérationnels, Risques Financiers, Risques Stratégiques, Risques de Conformité.
        3. Sous chaque catégorie, identifiez 2 à 3 risques spécifiques (titres ###) pertinents pour l'entreprise.
        4. Pour chaque risque, utilisez des puces pour proposer une brève description du risque et une ou deux mesures de contrôle ou d'atténuation possibles.
        """
    }
}

@app.route("/")
def index():
    return send_file('src/index.html')

@app.route("/generate", methods=["POST"])
def generate():
    try:
        description = request.form.get("description")
        map_type = request.form.get("map_type", "processus") # Default to 'processus'

        if not description:
            return jsonify({"error": "La description est requise"}), 400
        
        if map_type not in PROMPT_INSTRUCTIONS:
            return jsonify({"error": "Type de carte invalide"}), 400

        # Select the instructions based on map_type
        selected_map = PROMPT_INSTRUCTIONS[map_type]
        expert_role = selected_map["expert_role"]
        instructions = selected_map["instructions"].format(description=description)

        # Create the final prompt for the model
        prompt = f"""
        Vous êtes {expert_role} qui crée une cartographie d'entreprise.
        Générez une carte mentale en markdown, compatible avec Markmap, pour l'idée d'entreprise suivante : "{description}"

        Instructions:
        {instructions}
        
        RÈGLE CRITIQUE : N'incluez aucun texte, titre ou explication en dehors de la structure markdown demandée. Votre réponse DOIT commencer directement par le premier titre `#`. Ne pas inclure ```markdown.
        """

        # Generate the content
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Vous êtes un assistant expert qui génère des cartes mentales en markdown pour la cartographie d'entreprise."},
                {"role": "user", "content": prompt}
            ]
        )

        raw_map_data = response.choices[0].message.content
        cleaned_map_data = clean_response(raw_map_data)
        
        if not cleaned_map_data:
            return jsonify({"error": "La réponse de l'IA était vide ou ne contenait pas de carte valide. Veuillez réessayer."}), 500

        # Return the cleaned generated text
        return jsonify({"map": cleaned_map_data})

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": "Une erreur interne du serveur est survenue lors de la génération de la carte."}), 500

def clean_response(raw_text):
    """
    Cleans the AI response to ensure it's valid markdown for Markmap.
    """
    cleaned_text = raw_text.strip()
    
    # 1. Try to extract from a markdown code block
    match = re.search(r"```(?:markdown)?\n(.*?)\n```", cleaned_text, re.DOTALL)
    if match:
        cleaned_text = match.group(1).strip()
    else:
        # 2. If no code block, find the first markdown header and discard anything before it
        lines = cleaned_text.splitlines()
        first_md_line_index = next((i for i, line in enumerate(lines) if line.strip().startswith('#')), -1)
        if first_md_line_index != -1:
            cleaned_text = '\n'.join(lines[first_md_line_index:]).strip()
            
    return cleaned_text

def main():
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))

if __name__ == "__main__":
    main()
