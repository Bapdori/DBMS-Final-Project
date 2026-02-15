import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables (API keys) from the .env file
load_dotenv()

def get_openai_client():
    """
    Helper function: Initializes the OpenAI client instance.
    The client is created on-demand to ensure resources are only allocated when needed.
    Verifies the existence of the API key to prevent runtime crashes.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing in the local .env configuration!")
    return OpenAI(api_key=api_key)

def translate_symptoms_to_medical_terms(user_input: str):
    """
    Performs semantic mapping of natural language symptoms into controlled medical vocabulary.
    
    This function utilizes Large Language Models (LLM) to bridge the gap between 
    informal patient descriptions and the formal English medical nomenclature 
    found in clinical databases like SIDER, STITCH, or SNAP.
    """
    try:
        # Obtain the authenticated OpenAI client
        client = get_openai_client()
        
        # PROMPT ENGINEERING: 
        # The prompt defines a structured reasoning process for the LLM:
        # 1. Language Detection (Multilingual support)
        # 2. Semantic Analysis (Understanding the intent)
        # 3. Domain Mapping (Alignment with clinical terminology)
        prompt = f"""
        You are a multilingual medical assistant. A user describes symptoms in their native language: "{user_input}"
        
        1. Detect the language and understand the symptoms.
        2. Map these symptoms to the 3 most likely medical side-effect terms used in English databases like SIDER or SNAP.
        3. Translate your findings into standard English medical terminology.
        
        Respond ONLY with the English terms, separated by commas. No explanations.
        Example: "Kopfschmerzen" -> Output: Headache, Migraine, Cephalalgia
        """

        # API Call: GPT-4o is used for high semantic accuracy.
        # Temperature is set to 0.2 to ensure deterministic and consistent outputs.
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        # Post-processing: Parsing the comma-separated string into a Python list
        raw_content = response.choices[0].message.content
        terms = raw_content.split(",")
        
        # Clean up whitespace for database compatibility
        return [term.strip() for term in terms]
    
    except Exception as e:
        # Error handling for network issues or API authentication failures
        print(f"Internal LLM Service Error: {e}")
        return []