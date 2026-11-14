# Nexus Agency Cloud Runner — تشغيل الوكلاء سحابياً 100%

هذا المشروع مجهز ليعمل بشكل مستقل تماماً على سحابة GitHub Actions السحابية كل يوم الساعة **9:00 صباحاً بتوقيت مصر/الرياض**، بدون الحاجة لأن يكون جهازك مفتوحاً أو متصلاً بالإنترنت.

## كيف يعمل؟
1. في تمام الساعة 9:00 صباحاً، يستيقظ سيرفر GitHub السحابي تلقائياً.
2. يتم تشغيل سكريبت `nexus_daily_swarm.py` الذي يقوم بتشغيل مهام الوكلاء الأربعة:
   - البحث عن عملاء جدد في السوق الخليجي (السعودية والإمارات).
   - استخراج نقاط الضعف وثغرات التسريب.
   - تجهيز نصوص رسائل الواتساب والانستقرام.
   - إعداد بريفات مهام التصميم والمونتاج للتيم.
3. يرسل التقرير اليومي كاملاً إلى إيميل مدير الوكالة (`ahmed.morgan86@gmail.com`).
4. لا يتم نشر أو إرسال أي رسالة للعملاء، وتنتظر المنظومة اعتمادك للأسعار وأمر الإرسال.

## خطوات التفعيل في دقيقة واحدة:
1. أنشئ مستودعاً خاصاً جديداً (Private Repository) على حسابك في GitHub باسم `nexus-agency-cloud-runner`.
2. ارفع هذه الملفات إليه:
   ```bash
   git init
   git add .
   git commit -m "feat: initial nexus cloud swarm runner"
   git branch -M main
   git remote add origin https://github.com/ahmedmorgan86/nexus-agency-cloud-runner.git
   git push -u origin main
   ```
3. ادخل على **Settings > Secrets and variables > Actions** في المستودع وأضف:
   - `SMTP_USER`: إيميل الـ Gmail الخاص بك.
   - `SMTP_PASS`: كلمة مرور التطبيقات من جوجل (Google App Password).
   - `DIRECTOR_EMAIL`: `ahmed.morgan86@gmail.com`.
