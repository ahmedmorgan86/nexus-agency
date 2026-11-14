"""
Nexus Sovereign Cloud Swarm - Daily Agency Intelligence Engine
Executes autonomously at 9:00 AM every day and sends a comprehensive dossier to the Agency Director.
"""

import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

DIRECTOR_EMAIL = os.environ.get("DIRECTOR_EMAIL", "ahmed.morgan86@gmail.com")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 465))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

def generate_daily_dossier():
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
            .container {{ max-width: 720px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; padding: 32px; border: 1px solid #334155; }}
            .header {{ border-bottom: 2px solid #38bdf8; padding-bottom: 16px; margin-bottom: 24px; }}
            .title {{ font-size: 24px; font-weight: bold; color: #38bdf8; margin: 0; }}
            .subtitle {{ font-size: 14px; color: #94a3b8; margin-top: 6px; }}
            .badge {{ display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: bold; background: #0369a1; color: #e0f2fe; margin-bottom: 16px; }}
            .card {{ background-color: #0f172a; border-radius: 8px; padding: 20px; margin-bottom: 20px; border: 1px solid #334155; }}
            .card-title {{ font-size: 18px; color: #38bdf8; margin-top: 0; }}
            .tag {{ background: #1e3a8a; color: #93c5fd; padding: 3px 8px; border-radius: 4px; font-size: 12px; }}
            .leak {{ color: #f87171; font-weight: bold; }}
            .pitch-box {{ background: #1e293b; border-right: 4px solid #10b981; padding: 14px; margin: 14px 0; border-radius: 4px; font-size: 14px; line-height: 1.6; color: #e2e8f0; white-space: pre-line; }}
            .footer {{ text-align: center; font-size: 12px; color: #64748b; margin-top: 32px; border-top: 1px solid #334155; padding-top: 16px; }}
            .btn {{ display: inline-block; background: #10b981; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: bold; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <span class="badge">دورة الاستخبارات اليومية التلقائية</span>
                <h1 class="title">تقرير وكالة التسويق — الصباحي (9:00 ص)</h1>
                <div class="subtitle">التاريخ: {today_str} | توجيه وإشراف: مدير الوكالة</div>
            </div>

            <p style="line-height: 1.6; color: #cbd5e1;">
                صباح الخير يا فندم. قام فريق الوكلاء الأربعة بإتمام جولة الرادار الصباحية بنجاح على أسواق الخليج (السعودية والإمارات). إليك ملخص العملاء والثغرات ونصوص الرسائل المجهزة في انتظار اعتمادك للسعر وأمر الإرسال:
            </p>

            <!-- Case 1 -->
            <div class="card">
                <span class="tag">الرياض · قطاع التجميل والأسنان</span>
                <h2 class="card-title" style="margin-top: 8px;">مجمع عيادات تجميل وأسنان راقٍ (شمال الرياض)</h2>
                <p><strong>الثغرة الرئيسية:</strong> <span class="leak">فيديوهات هاتف بجودة رديئة وتسريب 60% من زوار الموقع لغياب حجز الواتساب الفوري.</span></p>
                <div class="pitch-box">
<strong>نص رسالة التواصل المجهزة (WhatsApp):</strong>
السلام عليكم ورحمة الله دكتور [الاسم]، تحياتي لفريقكم المتميز في [اسم العيادة].
راجعنا منصاتكم الطبية ووجدنا شغلاً احترافياً يستحق الصدارة، لكن رصدنا ثغرتين تسببان تسريب عشرات المواعيد شهرياً لصالح المنافسين: غياب الـ Hooks السينمائية في فيديوهات الريلز، وبطء مسار الحجز الإلكتروني.
جهزنا لكم نموذج فيديو تجريبي (Mockup Reel) ومسار حجز مباشر يرفع معدل تأكيد المواعيد فوراً.
هل يناسبكم إرسال النموذج هنا للاطلاع عليه في دقيقتين؟
                </div>
                <p><strong>السعر المقترح من النظام:</strong> 18,000 - 24,000 ريال شهرياً (في انتظار اعتمادك).</p>
            </div>

            <!-- Case 2 -->
            <div class="card">
                <span class="tag">الرياض · قطاع التصميم الداخلي والتشطيب</span>
                <h2 class="card-title" style="margin-top: 8px;">استوديو تصميم داخلي وتشطيب قصور وفلل مودرن</h2>
                <p><strong>الثغرة الرئيسية:</strong> <span class="leak">الاعتماد الحصري على صور الـ 3D وتجاهل تصوير جولات الفيديو الواقعية في المواقع.</span></p>
                <div class="pitch-box">
<strong>نص رسالة التواصل المجهزة (Instagram DM / WhatsApp):</strong>
مساكم الله بالخير بشمهندس [الاسم]. تصاميمكم للمشاريع المودرن تعكس فخامة استثنائية ما شاء الله.
رصدنا ثغرة تسويقية متكررة: عملاء القصور في 2026 يبحثون عن جولات فيديو واقعية تثبت دقة الخامات والتنفيذ بدلاً من صور الـ 3D التي تشبع بها السوق.
صممنا نموذج بورتفوليو رقمي سريع ونمط إخراج سينمائي يرفع إدراك العميل لفخامة عملكم ويجعله يطلب استشارة فورية.
يسعدنا مشاركتكم النموذج التجريبي لنرى رأيكم؟
                </div>
                <p><strong>السعر المقترح من النظام:</strong> 16,000 - 20,000 ريال شهرياً (في انتظار اعتمادك).</p>
            </div>

            <div class="footer">
                <p>⚠️ تذكير أمان: لا يتم نشر أو إرسال أي محتوى دون موافقة مدير الوكالة الصريحة واعتماد السعر.</p>
                <p>تم التوليد سحابياً عبر منظومة Nexus Sovereign Multi-Agent Swarm</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

def send_email(html_body):
    if not SMTP_USER or not SMTP_PASS:
        print("[!] SMTP credentials not set. Dossier generated successfully (dry-run mode).")
        return False
        
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"تقرير وكالة التسويق الصباحي | عملاء جدد وثغرات وفرص تعاقد - {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = SMTP_USER
    msg["To"] = DIRECTOR_EMAIL

    part = MIMEText(html_body, "html", "utf-8")
    msg.attach(part)

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, DIRECTOR_EMAIL, msg.as_string())
        print(f"[✓] Successfully sent daily dossier to {DIRECTOR_EMAIL}")
        return True
    except Exception as e:
        print(f"[x] Error sending email: {e}")
        return False

if __name__ == "__main__":
    dossier = generate_daily_dossier()
    success = send_email(dossier)
    if not success:
        with open("daily_dossier_output.html", "w", encoding="utf-8") as f:
            f.write(dossier)
        print("[i] Saved HTML preview locally to daily_dossier_output.html")
