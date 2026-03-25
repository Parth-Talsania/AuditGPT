"""
Explainable AI Engine for AuditGPT.

Uses Google Gemini to generate human-readable explanations of forensic findings.
Falls back to template-based generation if API key is unavailable.
"""

import os
from typing import List, Dict, Any, Optional

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load from .env file in project root
except ImportError:
    pass  # dotenv not installed, rely on system env vars

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class ExplainableAIEngine:
    """
    Generates AI-powered explanations for forensic analysis results.
    
    Uses Google Gemini (gemini-2.0-flash) for intelligent synthesis.
    Falls back to template-based generation if API unavailable.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the XAI engine.
        
        Args:
            api_key: Gemini API key. If not provided, reads from GEMINI_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = None
        self._initialized = False
        
        if self.api_key and GEMINI_AVAILABLE:
            try:
                genai.configure(api_key=self.api_key)
                # Use gemini-2.0-flash (latest stable model)
                self.model = genai.GenerativeModel('gemini-2.0-flash')
                self._initialized = True
            except Exception as e:
                print(f"[XAI] Failed to initialize Gemini: {e}")
                self._initialized = False
    
    def generate_executive_summary(
        self,
        company: str,
        sector: str,
        dual_score: Dict[str, Any],
        signals: List[Dict[str, Any]],
    ) -> str:
        """
        Generate an executive summary explaining the dual score.
        
        Args:
            company: Company ticker
            sector: Company sector
            dual_score: Dict with manipulation_score, stress_score, combined_score
            signals: List of detected signals with severity and descriptions
            
        Returns:
            Human-readable 4-sentence explanation
        """
        if self._initialized and self.model:
            return self._generate_with_gemini(company, sector, dual_score, signals)
        else:
            return self._generate_fallback(company, sector, dual_score, signals)
    
    def _generate_with_gemini(
        self,
        company: str,
        sector: str,
        dual_score: Dict[str, Any],
        signals: List[Dict[str, Any]],
    ) -> str:
        """Generate summary using Gemini API."""
        # Build signal summary for prompt
        signal_descriptions = []
        for s in signals[:10]:  # Limit to top 10 signals
            desc = f"- [{s.get('severity', 'MEDIUM')}] {s.get('description', 'Unknown signal')}"
            signal_descriptions.append(desc)
        
        signals_text = "\n".join(signal_descriptions) if signal_descriptions else "No significant signals detected."
        
        prompt = f"""You are a Chief Forensic Auditor analyzing {company} ({sector} sector).

DUAL SCORE RESULTS:
- Manipulation/Fraud Risk Score: {dual_score.get('manipulation_score', 0)}/100 ({dual_score.get('manipulation_level', 'LOW')})
- Financial Stress Score: {dual_score.get('stress_score', 0)}/100 ({dual_score.get('stress_level', 'LOW')})
- Combined Forensic Score: {dual_score.get('combined_score', 0)}/100 ({dual_score.get('combined_level', 'LOW')})

DETECTED SIGNALS:
{signals_text}

TASK: Write exactly 4 sentences that explain WHY this company received these scores, strictly based on the signals provided above. Do not invent any information. Be concise and professional.

Format: Return only the 4 sentences, no headers or bullet points."""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=300,
                    temperature=0.3,
                )
            )
            return response.text.strip()
        except Exception as e:
            print(f"[XAI] Gemini generation failed: {e}")
            return self._generate_fallback(company, sector, dual_score, signals)
    
    def _generate_fallback(
        self,
        company: str,
        sector: str,
        dual_score: Dict[str, Any],
        signals: List[Dict[str, Any]],
    ) -> str:
        """Generate template-based summary when API unavailable."""
        manip_score = dual_score.get('manipulation_score', 0)
        stress_score = dual_score.get('stress_score', 0)
        combined_level = dual_score.get('combined_level', 'LOW')
        
        # Count signals by severity
        critical_count = sum(1 for s in signals if s.get('severity') == 'CRITICAL')
        high_count = sum(1 for s in signals if s.get('severity') == 'HIGH')
        
        # Build sentences based on scores
        sentences = []
        
        # Sentence 1: Overall assessment
        if combined_level == 'CRITICAL':
            sentences.append(f"{company} shows critical forensic risk requiring immediate investigation.")
        elif combined_level == 'HIGH':
            sentences.append(f"{company} exhibits elevated forensic risk warranting close monitoring.")
        elif combined_level == 'MEDIUM':
            sentences.append(f"{company} shows moderate forensic risk with some areas of concern.")
        else:
            sentences.append(f"{company} demonstrates a relatively healthy forensic profile.")
        
        # Sentence 2: Manipulation vs Stress breakdown
        if manip_score > stress_score + 20:
            sentences.append(f"The primary concern is potential manipulation with a score of {manip_score:.0f}/100, significantly exceeding stress indicators.")
        elif stress_score > manip_score + 20:
            sentences.append(f"Financial stress dominates with a score of {stress_score:.0f}/100, suggesting genuine business pressure rather than manipulation.")
        else:
            sentences.append(f"Both manipulation ({manip_score:.0f}/100) and stress ({stress_score:.0f}/100) scores are elevated, indicating a complex risk profile.")
        
        # Sentence 3: Key signals
        if critical_count > 0:
            top_critical = next((s for s in signals if s.get('severity') == 'CRITICAL'), None)
            if top_critical:
                # Handle empty description strings - use description or fallback
                desc = top_critical.get('description', '') or 'critical signal detected'
                sentences.append(f"The most severe finding is: {desc[:100]}.")
            else:
                sentences.append("Critical severity signals were detected requiring immediate attention.")
        elif high_count > 0:
            top_high = next((s for s in signals if s.get('severity') == 'HIGH'), None)
            if top_high:
                # Handle empty description strings - use description or fallback
                desc = top_high.get('description', '') or 'elevated risk indicator'
                sentences.append(f"A notable concern is: {desc[:100]}.")
            else:
                sentences.append("High severity signals were detected warranting close monitoring.")
        else:
            sentences.append("No critical or high-severity signals were detected in this analysis.")
        
        # Sentence 4: Sector context
        if sector == 'BANK':
            sentences.append("As a banking entity, asset quality and capital adequacy metrics were given priority in this assessment.")
        elif sector == 'IT':
            sentences.append("For this IT services company, cash flow quality and receivables management were key focus areas.")
        else:
            sentences.append("Standard forensic analysis protocols were applied across all financial dimensions.")
        
        return " ".join(sentences)
    
    def is_available(self) -> bool:
        """Check if Gemini API is available."""
        return self._initialized


# Singleton instance for easy import
xai_engine = ExplainableAIEngine()
