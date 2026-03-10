import os
import json
import openai
import pdfplumber
import docx

def extract_text_from_file(file_path, filename):
    """Extract text from PDF or DOCX file."""
    text = ""
    ext = os.path.splitext(filename)[1].lower()
    
    try:
        if ext == '.pdf':
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
        elif ext == '.docx':
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            return None, "Unsupported file format. Please upload PDF or DOCX."
    except Exception as e:
        return None, f"Error reading file: {str(e)}"
        
    if not text.strip():
        return None, "Could not extract readable text from the file."
        
    return text.strip(), None

def generate_workshop_content(topic=None, duration=None, file_text=None):
    """
    Generates structured workshop content (JSON) using AI.
    Inputs:
        topic (str): The workshop topic/technology (Scenario 1)
        duration (str): E.g. '2 Days', '16 Hours'
        file_text (str): Extracted text from uploaded document (Scenario 2)
    Returns:
        dict: Parsed JSON with title, subtitle, category, description, outcomes, target_audience, agenda.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OpenAI API Key not configured."}

    client = openai.OpenAI(api_key=api_key)

    system_prompt = (
        "You are an elite Instructional Designer and Technical Curriculum Architect. "
        "Your task is to generate professional, compelling content for an open-enrollment corporate training workshop. "
        "The output MUST be a strict JSON object with the following keys:\n"
        "1. 'title': A highly professional, catchy workshop title (max 60 chars).\n"
        "2. 'subtitle': A brief, compelling one-liner tagline (max 100 chars).\n"
        "3. 'category': MUST be exactly one of: ['Leadership', 'Technical', 'Soft Skills', 'AI & Technology', 'Finance & Strategy', 'HR & L&D', 'Sales', 'Communication', 'General'].\n"
        "4. 'description': Exactly 3-5 powerful bullet points (one per line, raw text, no markers) explaining the value proposition. Do NOT use paragraphs.\n"
        "5. 'outcomes': Exactly 3-5 actionable learning outcomes. Return as a SINGLE string with each outcome separated by a newline (\\n). Do NOT use bullet points or asterisks, just the raw text per line.\n"
        "6. 'target_audience': Exactly 3-5 bullet points (one per line, raw text, no markers) stating who should attend and any prerequisites.\n"
        "7. 'agenda': A detailed markdown-formatted agenda/schedule broken down by SESSION or HOURS. \n"
        "\nCRITICAL CONSTRAINTS (MANDATORY):\n"
        "- NO 'DAYS' IN AGENDA: Do NOT use 'Day 1', 'Day 2', etc. Use 'Session 1', 'Session 2', or 'Hour 1-4', 'Hour 5-8', etc.\n"
        "- DURATION RIGOR: The agenda content MUST strictly sum up to the requested duration (e.g., if 16 hours, ensure the sessions/modules effectively cover 16 clock-hours of content). \n"
        "- MAX 5 POINTERS: 'description', 'outcomes', and 'target_audience' MUST have exactly 3 to 5 distinct points each. No more, no less.\n"
        "- CONTENT FIDELITY: When a document is provided, strictly use its content to fill the requested duration. Do not create ad-hoc content that contradicts the requested hours.\n"
        "Return raw JSON only."
    )

    if file_text:
        user_prompt = (
            f"Please generate a workshop outline based on the following trainer's content document.\n"
            f"Target Duration: {duration if duration else 'Unspecified'}\n\n"
            f"--- CONTENT SOURCE ---\n{file_text[:15000]}  # Truncated to avoid token limits"
        )
    else:
        user_prompt = (
            f"Please generate a workshop outline from scratch.\n"
            f"Topic/Technology: {topic}\n"
            f"Target Duration: {duration}\n\n"
            f"Build a comprehensive, industry-standard curriculum for this topic."
        )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content.strip()
        return json.loads(result_text)

    except Exception as e:
        print(f"AI Workshop Generation Error: {e}")
        return {"error": f"Failed to generate content: {str(e)}"}
