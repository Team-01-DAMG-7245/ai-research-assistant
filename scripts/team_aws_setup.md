# AWS Setup for aiRA Project Team

## Your AWS Credentials

I've created IAM users for everyone with S3 access. Check your secure message for:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY

⚠️ **Security Rules:**
- Never commit these to Git
- Never share them publicly
- Never push them to GitHub
- Keep them only in your local .env file

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <repo-url>
cd aiRA-research-assistant
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Mac/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Your Credentials
```bash
# Copy the example env file
cp .env.example .env
```

**Edit `.env` with your credentials:**
```properties
# AWS Configuration
AWS_ACCESS_KEY_ID=AKIA...  # Your access key from Natnicha
AWS_SECRET_ACCESS_KEY=...   # Your secret key from Natnicha
AWS_REGION=us-east-1
S3_BUCKET_NAME=aira-project-bucket

# Leave these blank for now (we'll add them in M3)
OPENAI_API_KEY=
PINECONE_API_KEY=
```

### 5. Test Your Access
```bash
python scripts/test_m1.py
```

**Expected output:**
```
🧪 Testing M1 Dependencies...

1️⃣ Environment Variables:
   ✅ AWS_ACCESS_KEY_ID: AKIA****...
   ✅ S3_BUCKET_NAME: aira-project-bucket

2️⃣ AWS S3 Connection:
   ✅ Connected (X buckets found)

3️⃣ arXiv API:
   ✅ Connected (test paper: ...)

4️⃣ PDF Processing (PyMuPDF):
   ✅ PyMuPDF version: 1.23.26

==================================================
🎉 M1 Setup Complete! Ready to start M2.
```

### 6. Verify S3 Bucket Access
```bash
python scripts/setup_s3.py
```

Should show:
```
ℹ️  Bucket already exists: aira-project-bucket
✅ All folders created
```

---

## Troubleshooting

### "InvalidAccessKeyId" error
- Double-check your AWS_ACCESS_KEY_ID in .env
- Make sure there are no extra spaces
- Make sure no quotes around the values

### "SignatureDoesNotMatch" error
- Check AWS_SECRET_ACCESS_KEY is correct
- Copy-paste carefully from the CSV file

### "Access Denied" error
- Ask Natnicha to verify you're in the user group
- Might need to wait a few minutes for AWS to propagate permissions

### "Bucket not found"
- Verify S3_BUCKET_NAME=aira-project-bucket (no typos)
- Make sure Natnicha ran setup_s3.py first

---

## Working Together

### Git Workflow
```bash
# Always pull before starting work
git pull origin main

# Create a feature branch
git checkout -b feature/your-feature-name

# Make your changes, then:
git add .
git commit -m "Description of changes"
git push origin feature/your-feature-name

# Create a Pull Request on GitHub for review
```

### File Organization
```
Your responsibilities:
- Natnicha: Data Engineering, ETL pipelines, S3, backend
- Swara: LLM integration, agents, RAG system
- Kundana: Frontend, testing, documentation

Don't edit each other's core files without discussion!
```

---

## Need Help?

1. Check if your issue is in Troubleshooting above
2. Ask in our team chat
3. Check AWS IAM console to verify your user exists
4. Make sure you're in the aiRA user group

## Security Reminder 🔒

**Never commit these files:**
- .env
- *.csv (AWS credentials)
- Any file with "key" or "secret" in the name

**Our .gitignore already covers this, but double-check!**