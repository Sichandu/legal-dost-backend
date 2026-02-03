"""
Legal Dost Backend - Fresh Clean Version
Author: Built for 23-year-old entrepreneur
Version: 2.0 - Guaranteed Working
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import io
import re
import json
from pathlib import Path

# Image processing
from PIL import Image

# PDF processing
try:
    import PyPDF2
except:
    PyPDF2 = None

# Google Gemini
try:
    import google.generativeai as genai
except:
    genai = None

# Environment variables
from dotenv import load_dotenv

# ============================================
# CONFIGURATION
# ============================================

# Load .env file
env_file = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_file)

# Get API key
API_KEY = os.getenv('GEMINI_API_KEY', '').strip()

print("\n" + "="*60)
print("🚀 LEGAL DOST - STARTING UP")
print("="*60)

# Check if .env exists
if env_file.exists():
    print(f"✅ Found .env file at: {env_file}")
else:
    print(f"❌ .env file NOT found at: {env_file}")
    print("   Create a .env file in backend folder with:")
    print("   GEMINI_API_KEY=your_key_here")

# Check API key
if API_KEY and len(API_KEY) > 20:
    print(f"✅ API Key loaded (length: {len(API_KEY)})")
    print(f"   Starts: {API_KEY[:15]}...")
    
    # Configure Gemini
    if genai:
        genai.configure(api_key=API_KEY)
        
        # Try to initialize model
#         try:
#             # Try gemini-pro first (most compatible)
#             model = genai.GenerativeModel('gemini-pro')
#             # Test it works
#             test = model.generate_content("Hi")
#             print(f"✅ Gemini Model: gemini-pro (working)")
#             MODEL_READY = True
#         except Exception as e:
#             print(f"❌ Model initialization failed: {e}")
#             model = None
#             MODEL_READY = False
#     else:
#         print("❌ google-generativeai package not installed")
#         model = None
#         MODEL_READY = False
# else:
#     print("❌ API Key not found or invalid")
#     print("   Add GEMINI_API_KEY to .env file")
#     model = None
#     MODEL_READY = False

# print("="*60 + "\n")
try:
    # List all available models
    print("🔍 Searching for available models...")
    available_models = []
    
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            model_name = m.name.split('/')[-1]  # Extract just the model name
            available_models.append(model_name)
            print(f"   Found: {model_name}")
    
    if not available_models:
        raise Exception("No compatible models found")
    
    # Try models in order of preference
    model_priority = [
        'gemini-1.5-flash-latest',
        'gemini-1.5-pro-latest', 
        'gemini-pro',
        'gemini-1.5-flash',
        'gemini-1.5-pro'
    ]
    
    model = None
    for preferred in model_priority:
        if preferred in available_models:
            try:
                model = genai.GenerativeModel(preferred)
                # Test it
                test = model.generate_content("Hi")
                print(f"✅ Using model: {preferred}")
                MODEL_READY = True
                break
            except:
                continue
    
    # If priority list didn't work, use first available
    if not model and available_models:
        model_name = available_models[0]
        model = genai.GenerativeModel(model_name)
        print(f"✅ Using model: {model_name}")
        MODEL_READY = True
    
    if not model:
        raise Exception("Could not initialize any model")
        
except Exception as e:
    print(f"❌ Model initialization failed: {e}")
    model = None
    MODEL_READY = False

# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(
    title="Legal Dost API",
    description="AI-powered legal notice analysis for Indian citizens",
    version="2.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# DATA MODELS
# ============================================

class AnalysisResult(BaseModel):
    notice_type: str
    main_issue: str
    deadline: str
    urgency: str
    explanation: str
    action_steps: List[str]
    extracted_text: str

# ============================================
# HELPER FUNCTIONS
# ============================================

def extract_from_image(img_bytes: bytes) -> str:
    """Extract text from image using Gemini Vision"""
    
    if not MODEL_READY:
        raise HTTPException(500, "AI model not ready. Check API key.")
    
    try:
        # Open image
        img = Image.open(io.BytesIO(img_bytes))
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Use Gemini to extract text
        prompt = "Extract all text from this image. Return only the text, nothing else."
        response = model.generate_content([prompt, img])
        
        text = response.text.strip()
        
        if len(text) < 20:
            raise HTTPException(400, "Could not extract enough text. Use clearer image.")
        
        return text
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Image extraction error: {e}")
        raise HTTPException(500, f"Image processing failed: {str(e)}")


def extract_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF"""
    
    if not PyPDF2:
        raise HTTPException(500, "PDF support not available")
    
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
        text = text.strip()
        
        if len(text) < 20:
            raise HTTPException(400, "PDF has no readable text. Try uploading as image.")
        
        return text
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"PDF extraction error: {e}")
        raise HTTPException(500, f"PDF processing failed: {str(e)}")


def analyze_with_ai(text: str) -> AnalysisResult:
    """Analyze legal notice with Gemini"""
    
    if not MODEL_READY:
        raise HTTPException(500, "AI model not ready")
    
    # Limit text length
    text = text[:4000]
    
    prompt = f"""You are a legal expert helping Indian citizens understand legal notices.

Analyze this notice and respond with ONLY a JSON object (no markdown, no explanation):

NOTICE TEXT:
{text}

Return this exact JSON structure:
{{
  "notice_type": "GST Notice / Court Summon / Employment Notice / Consumer Complaint / Traffic Challan / Property Dispute / Income Tax Notice / Other",
  "main_issue": "मुख्य समस्या को 1-2 lines में Hindi में explain करें",
  "deadline": "DD-MM-YYYY format में deadline, या 'कोई deadline नहीं' if not mentioned",
  "urgency": "high or medium or low (based on deadline and consequences)",
  "explanation": "इस notice का मतलब क्या है - 3-4 sentences में सरल Hindi में समझाएं। Common person को समझ आए ऐसी भाषा use करें।",
  "action_steps": [
    "पहला step क्या करना है",
    "दूसरा step क्या करना है", 
    "तीसरा step क्या करना है"
  ]
}}

Remember: Return ONLY the JSON object, no other text before or after."""

    try:
        # Call Gemini
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        # Clean response
        raw_text = raw_text.replace('```json', '').replace('```', '').strip()
        
        # Find JSON in response
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            raw_text = json_match.group()
        
        # Parse JSON
        data = json.loads(raw_text)
        
        # Validate and set defaults
        result = AnalysisResult(
            notice_type=data.get('notice_type', 'अज्ञात'),
            main_issue=data.get('main_issue', 'विश्लेषण नहीं हो पाया'),
            deadline=data.get('deadline', 'कोई deadline नहीं'),
            urgency=data.get('urgency', 'medium'),
            explanation=data.get('explanation', 'Notice का detailed analysis नहीं हो पाया। कृपया lawyer से संपर्क करें।'),
            action_steps=data.get('action_steps', ['Notice सुरक्षित रखें', 'Lawyer से परामर्श लें', 'Related documents तैयार रखें']),
            extracted_text=text
        )
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing failed: {e}")
        print(f"Raw AI response: {raw_text[:500]}")
        
        # Return fallback
        return AnalysisResult(
            notice_type="विश्लेषण में त्रुटि",
            main_issue="AI response को process नहीं कर पाए",
            deadline="कोई deadline नहीं",
            urgency="medium",
            explanation="आपका legal notice प्राप्त हुआ है। Automatic analysis में technical issue आई है। बेहतर होगा कि आप किसी lawyer से इसे check करवा लें।",
            action_steps=[
                "Notice की photocopy सुरक्षित रखें",
                "किसी अनुभवी lawyer से परामर्श लें", 
                "सभी संबंधित documents इकट्ठा करें"
            ],
            extracted_text=text
        )
        
    except Exception as e:
        print(f"AI analysis error: {e}")
        raise HTTPException(500, f"Analysis failed: {str(e)}")

# ============================================
# API ENDPOINTS
# ============================================

@app.get("/")
def root():
    """Health check"""
    return {
        "service": "Legal Dost API",
        "version": "2.0",
        "status": "running",
        "ai_ready": MODEL_READY,
        "message": "समझो अपने Rights - Legal notices को simple Hindi में समझें"
    }


@app.get("/health")
def health_check():
    """Detailed health check"""
    return {
        "api_running": True,
        "env_file_exists": env_file.exists(),
        "api_key_loaded": bool(API_KEY and len(API_KEY) > 20),
        "gemini_ready": MODEL_READY,
        "pdf_support": PyPDF2 is not None
    }


@app.get("/test")
def test_ai():
    """Test if AI is working"""
    
    if not MODEL_READY:
        return {
            "status": "error",
            "message": "Gemini AI not initialized. Check your API key in .env file",
            "api_key_present": bool(API_KEY),
            "api_key_length": len(API_KEY) if API_KEY else 0
        }
    
    try:
        response = model.generate_content("Say नमस्ते in one word")
        return {
            "status": "success",
            "ai_response": response.text,
            "message": "Gemini AI is working perfectly!"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@app.post("/analyze", response_model=AnalysisResult)
async def analyze_notice(file: UploadFile = File(...)):
    """
    Analyze legal notice - AI INFORMATION ONLY, NOT LEGAL ADVICE
    Upload legal notice (image or PDF) and get AI analysis
    
    Supported formats: JPG, PNG, PDF
    """
    
    print(f"\n📄 Processing: {file.filename}")
    
    # Check file type
    allowed = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'application/pdf']
    
    if file.content_type not in allowed:
        raise HTTPException(400, "Invalid file. Upload JPG, PNG, or PDF only.")
    
    try:
        # Read file
        file_data = await file.read()
        print(f"📦 File size: {len(file_data)} bytes")
        
        # Extract text
        if file.content_type.startswith('image/'):
            text = extract_from_image(file_data)
            print(f"✅ Extracted from image: {len(text)} chars")
        else:
            text = extract_from_pdf(file_data)
            print(f"✅ Extracted from PDF: {len(text)} chars")
        
        # Analyze
        result = analyze_with_ai(text)
        print(f"✅ Analysis complete: {result.notice_type}\n")

        result.explanation = (
        f"⚠️ यह AI-generated जानकारी है, legal advice नहीं। "
        f"{result.explanation} "
        f"किसी भी action से पहले qualified lawyer से परामर्श अवश्य लें।"
    )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(500, f"Processing failed: {str(e)}")


# ============================================
# RUN SERVER
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    print("\n🌐 Starting server on http://localhost:8000")
    print("📚 API docs at http://localhost:8000/docs")
    print("🧪 Test AI at http://localhost:8000/test\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)