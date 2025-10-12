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

@app.route("/")
def index():
    return send_file('src/index.html')

@app.route("/generate", methods=["POST"])
def generate():
    try:
        # Get the business description from the request form
        description = request.form.get("description")
        if not description:
            return jsonify({"error": "Description is required"}), 400

        # Create the prompt for the model
        prompt = f"""
        You are an expert business consultant creating a business model canvas.
        Generate a markdown mind map, compatible with Markmap, for the following business idea: "{description}"

        Instructions:
        1. The business idea "{description}" must be the central root of the mind map (the main # heading).
        2. Create 9 main branches (## headings) for the sections of the Business Model Canvas: Key Partners, Key Activities, Key Resources, Value Propositions, Customer Relationships, Channels, Customer Segments, Cost Structure, and Revenue Streams.
        3. Under each of the 9 branches, generate 2 to 4 concise bullet points that are directly relevant to the business idea.
        4. CRITICAL: Do not include any text, titles, or explanations outside of the markdown structure. The output must start directly with the first `#` heading. Do not include ```markdown.
        """

        # Generate the content
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates markdown mind maps."},
                {"role": "user", "content": prompt}
            ]
        )

        raw_map_data = response.choices[0].message.content

        # --- Robust Cleaning of the AI Response ---
        cleaned_map_data = raw_map_data.strip()

        # 1. Try to extract from a markdown code block
        match = re.search(r"```(?:markdown)?\n(.*?)\n```", cleaned_map_data, re.DOTALL)
        if match:
            cleaned_map_data = match.group(1).strip()
        else:
            # 2. If no code block, find the first markdown header and discard anything before it
            lines = cleaned_map_data.splitlines()
            first_md_line_index = next((i for i, line in enumerate(lines) if line.strip().startswith('#')), -1)
            if first_md_line_index != -1:
                cleaned_map_data = '\n'.join(lines[first_md_line_index:]).strip()
        
        # 3. Final check for empty content
        if not cleaned_map_data:
            return jsonify({"error": "The AI response was empty or did not contain a valid mind map. Please try again."}), 500

        # Return the cleaned generated text
        return jsonify({"map": cleaned_map_data})

    except Exception as e:
        # Log the error for debugging
        print(f"An error occurred: {e}")
        # Return a generic error message to the user
        return jsonify({"error": "An internal server error occurred while generating the map."}), 500

def main():
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))

if __name__ == "__main__":
    main()
