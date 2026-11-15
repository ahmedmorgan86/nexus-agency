"""
NEXUS OS — Sales Intelligence Agent
Manages CRM pipeline states, generates personalized strategic proposals,
and drafts tailored multi-channel outreach pitches (WhatsApp / Email).
"""

from typing import Dict, Any

# Formal CRM Pipeline States
STAGE_DISCOVERED = "DISCOVERED"
STAGE_ANALYZED = "ANALYZED"
STAGE_QUALIFIED = "QUALIFIED"
STAGE_DEMO_CREATED = "DEMO_CREATED"
STAGE_APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
STAGE_CONTACTED = "CONTACTED"
STAGE_RESPONDED = "RESPONDED"
STAGE_NEGOTIATION = "NEGOTIATION"
STAGE_WON = "WON"
STAGE_LOST = "LOST"

class SalesIntelligenceAgent:
    def __init__(self):
        self.agent_name = "SALES_INTELLIGENCE_AGENT"

    def generate_personalized_proposal(self, lead: Dict[str, Any], score_data: Dict[str, Any], audit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a structured, client-specific marketing growth blueprint and proposal.
        """
        name = lead.get("name") or "العميل المستهدف"
        sector = lead.get("sector") or "القطاع التجاري"
        price = lead.get("benchmark_price") or "$4,000 USD"
        score = score_data.get("total_score", 85)
        findings = audit_data.get("findings", [])

        # Build Customized Deliverables Plan
        deliverables = [
            "1. إعادة هيكلة مسار التحويل وإطلاق صفحة هبوط 4K فائقة السرعة.",
            "2. إنتاج 8 مقاطع ريلز وفيديو إعلاني سينمائي عالي الجودة بنسبة أبعاد 9:16.",
            "3. إدارة وتوجيه الحملات الممولة باستهداف دقيق يقلل تكلفة الاستحواذ بنسبة تصل إلى 30%.",
            "4. ربط مسار تحويل فوري عبر واتساب للرد على العملاء المحتملين خلال 60 ثانية."
        ]

        # WhatsApp Direct Pitch
        whatsapp_pitch = (
            f"مرحباً فريق {name}،\n"
            f"معكم أحمد مرجان — المدير التنفيذي لوكالة NEXUS العالمية.\n\n"
            f"أجرينا تحليلاً تسويقياً شاملاً لأداء منصتكم في قطاع ({sector})، "
            f"ورصدنا فرصة مؤكدة لمعالجة تسرب الزوار ومضاعفة معدل التحويل إلى طلبات فعلية.\n\n"
            f"أعددنا لسيادتكم دراسة جدوى موجزة تتضمن نماذج بصرية مخصصة ومسار نمو متكامل.\n"
            f"هل يناسبكم الاطلاع على ملخص الخطة التفاعلي؟"
        )

        # Email Executive Pitch
        email_pitch = {
            "subject": f"خطة مضاعفة العائد الإعلاني وتطوير مسار التحويل — مقترح خاص لـ {name}",
            "body_html": f"""
            <div dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b;">
                <p>عناية السادة مسؤولي النمو في <strong>{name}</strong> المحترمين،</p>
                <p>تحية طيبة وبعد،</p>
                <p>يسعدنا في وكالة <strong>NEXUS</strong> تقديم هذا التقرير الاستراتيجي الموجز بعد تدقيق مسار التسويق الرقمي لنشاطكم المتميز في قطاع {sector}.</p>
                <div style="background: #f8fafc; border-right: 4px solid #8b5cf6; padding: 14px; margin: 16px 0; border-radius: 6px;">
                    <strong>أبرز الفرص المرصودة لزيادة المبيعات:</strong>
                    <ul>
                        {''.join([f"<li>{f.get('remedy', '')}</li>" for f in findings])}
                    </ul>
                </div>
                <p>الباقة المقترحة للتعاقد الأولي: <strong>{price} شهرياً</strong> مع ضمان تسليم كافة المخرجات والمتابعة الأسبوعية للأداء.</p>
                <p>يسعدنا ترتيب مكالمة استكشافية موجزة أو إرسال الرابط التفاعلي الكامل للعرض.</p>
                <p>وتفضلوا بقبول فائق التقدير والاحترام،<br><strong>أحمد مرجان</strong><br>المدير التنفيذي — NEXUS Agency<br>هاتف/واتساب: +201210237652</p>
            </div>
            """
        }

        return {
            "agent": self.agent_name,
            "lead_id": lead.get("id"),
            "qualification_score": score,
            "deliverables": deliverables,
            "benchmark_investment": price,
            "whatsapp_pitch": whatsapp_pitch,
            "email_pitch": email_pitch,
            "next_pipeline_stage": STAGE_QUALIFIED,
            "tokens_used": 180,
            "qa_score": 96
        }
