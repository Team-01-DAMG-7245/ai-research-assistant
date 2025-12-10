# EC2 Deployment Guide

This guide walks you through deploying the AI Research Assistant on AWS EC2.

## Prerequisites

- AWS account with EC2 access
- EC2 instance (recommended: t3.medium or larger, 4GB+ RAM)
- SSH access to your EC2 instance
- Docker and Docker Compose installed (or we'll install them)

## Do I Need a VPC?

**Short answer: No, you don't need to create a custom VPC.**

### Default VPC (Recommended for This Project)

AWS automatically provides a **default VPC** in each region when you create an AWS account. This is sufficient for deploying this AI Research Assistant:

- ✅ **Single EC2 instance** - Works perfectly in default VPC
- ✅ **Public internet access** - Your instance can access S3, Pinecone, OpenAI APIs
- ✅ **Simple security** - Security groups handle firewall rules
- ✅ **No extra cost** - Default VPC is free
- ✅ **Easy setup** - No additional configuration needed

**When launching your EC2 instance, AWS will automatically use the default VPC** - you don't need to do anything special.

### When You WOULD Need a Custom VPC

You'd only need to create a custom VPC if you need:
- **Multi-tier architecture** (public/private subnets, NAT gateways)
- **Multiple availability zones** with specific networking
- **VPN connections** to on-premises networks
- **Compliance requirements** (HIPAA, PCI-DSS, etc.)
- **Complex security** (network ACLs, VPC peering, etc.)
- **Load balancers** across multiple subnets

**For this project**: The default VPC is perfect. Focus on configuring your **Security Group** (firewall rules) instead.

### I Deleted My Default VPC - How Do I Create a New One?

If you accidentally deleted your default VPC, you have two options:

#### Option 1: Recreate Default VPC (Easiest)

AWS allows you to recreate the default VPC in a region:

1. **Go to AWS Console → VPC Dashboard**
2. **Click "Actions" → "Create Default VPC"**
3. **Select your region** (if you have multiple regions)
4. **Click "Create Default VPC"**

AWS will automatically create:
- ✅ Default VPC with CIDR block (172.31.0.0/16)
- ✅ Default subnets in each availability zone
- ✅ Internet gateway attached
- ✅ Default route table with internet gateway route
- ✅ Default security group
- ✅ Default network ACL

**This is the easiest option** and works exactly like the original default VPC.

#### Option 2: Create a Custom VPC (Manual Setup)

If Option 1 doesn't work or you prefer manual control:

1. **Create VPC**:
   - Go to VPC Dashboard → "Create VPC"
   - Name: `default-vpc` (or any name)
   - IPv4 CIDR: `10.0.0.0/16` (or `172.31.0.0/16` to match default)
   - Tenancy: Default
   - Click "Create VPC"

2. **Create Internet Gateway**:
   - VPC Dashboard → Internet Gateways → "Create Internet Gateway"
   - Name: `default-igw`
   - Click "Create Internet Gateway"
   - Select the gateway → Actions → "Attach to VPC"
   - Select your VPC → "Attach Internet Gateway"

3. **Create Subnets** (at least one in a public AZ):
   - VPC Dashboard → Subnets → "Create Subnet"
   - VPC: Select your VPC
   - Availability Zone: Choose one (e.g., `us-east-1a`)
   - IPv4 CIDR: `10.0.1.0/24` (or `172.31.1.0/24`)
   - **Enable "Auto-assign public IPv4 address"** ✅ (important!)
   - Click "Create Subnet"
   - Repeat for other AZs if needed

4. **Configure Route Table**:
   - VPC Dashboard → Route Tables
   - Find the main route table for your VPC
   - Click "Edit routes" → "Add route"
   - Destination: `0.0.0.0/0`
   - Target: Select your Internet Gateway
   - Click "Save changes"

5. **Verify Setup**:
   - Your VPC should now work like a default VPC
   - EC2 instances launched in your subnets will have internet access

**Quick Test**: Launch a test EC2 instance in your new VPC to verify it gets a public IP and can access the internet.

## Quick Start Checklist

- [ ] **Find your IPv4 address** (for security group configuration)
  ```bash
  curl -4 ifconfig.me  # From your local machine (use -4 for IPv4)
  # If you see IPv6 (starts with 2600:...), you need IPv4 instead
  ```
- [ ] Launch EC2 instance
- [ ] **Configure security groups**:
  - ✅ **Yes, you can use the default security group**
  - ⚠️ **But**: You must add inbound rules after creation (default blocks all inbound)
  - Or create a new security group during launch
- [ ] Install Docker and Docker Compose
- [ ] Transfer project files
- [ ] Configure environment variables
- [ ] Build and start services
- [ ] Verify deployment

> **⚠️ Security Note**: Always restrict security group rules to your specific IP address instead of `0.0.0.0/0` (all IPs). This prevents unauthorized access attempts.
>
> **💡 Quick Answer**: Yes, you can use the default security group, but you'll need to add SSH (22) and your app ports (8000, 8501) rules after instance creation.

---

## Step-by-Step Deployment

### Step 1: Launch EC2 Instance

1. **Go to AWS Console → EC2 → Launch Instance**
2. **Choose Instance Type**: 
   - Minimum: `t3.small` (2 vCPU, 2GB RAM)
   - Recommended: `t3.medium` (2 vCPU, 4GB RAM) or larger
   - For production: `t3.large` (2 vCPU, 8GB RAM) or better
3. **Choose AMI**: Amazon Linux 2023 or Ubuntu 22.04 LTS
4. **Network Settings**:
   - **VPC**: Use default VPC (automatically selected) ✅
   - **Subnet**: Use default subnet (automatically selected) ✅
   - **Auto-assign Public IP**: Enable (so you can SSH and access services)
5. **Configure Security Group**:
   
   **Option A: Use Default Security Group (Easiest)**
   - Select "default" security group from the dropdown
   - **⚠️ Important**: Default security group doesn't allow inbound traffic by default
   - You'll need to add rules after instance creation (see Step 5b below)
   
   **Option B: Create New Security Group (Recommended)**
   - Click "Create security group"
   - Name: `ai-research-sg` (or any name)
   - Description: "Security group for AI Research Assistant"
   - Then add rules below
   
   **⚠️ Security Best Practice**: Restrict access to your IP address instead of `0.0.0.0/0` (all IPs) for better security.
   
   **Find your IPv4 address:**
   ```bash
   # From your local machine (use -4 to force IPv4)
   curl -4 ifconfig.me
   # or
   curl -4 ipinfo.io/ip
   # or
   curl -4 https://api.ipify.org
   
   # If you see IPv6 (like 2600:4040:...), you need IPv4 (like 203.0.113.45)
   ```
   
   **Required Security Group Rules** (add these now or after creation):
   - **SSH (22)**: Your IP only (e.g., `203.0.113.45/32`)
   - **Custom TCP (8000)**: Your IP only (API)
   - **Custom TCP (8501)**: Your IP only (Streamlit)
   - **HTTP (80)**: Optional - Your IP only (if using Nginx)
   - **HTTPS (443)**: Optional - Your IP only (if using Nginx with SSL)
   
   **For Production/Public Access:**
   - If you need public access, consider using a load balancer or Nginx reverse proxy
   - Only open ports 80/443 publicly if using HTTPS with proper SSL certificates
   - Keep SSH (22) restricted to your IP **always**
   - Consider using AWS Systems Manager Session Manager instead of SSH for even better security
6. **Create/Select Key Pair**: 
   - Click "Create new key pair"
   - **Key pair type**: 
     - **ED25519** (recommended) - Modern, more secure, faster, smaller keys
     - **RSA** (also fine) - Traditional, widely compatible, works everywhere
   - **Key pair name**: `ai-research-key` (or any name)
   - **Key pair format**: `.pem` (for OpenSSH) or `.ppk` (for PuTTY on Windows)
   - Click "Create key pair" and **download the file** (you can't download it again!)
7. **Launch Instance**

> **Note**: AWS will automatically use your default VPC. No custom VPC setup needed!
>
> **Key Pair Recommendation**: Use **ED25519** for new deployments (more secure, faster). Use **RSA** if you need compatibility with older systems or tools.

### Step 1b: Configure Default Security Group (If You Used Default SG)

**Yes, you can use the default security group!** However, you need to add inbound rules because the default security group blocks all inbound traffic by default.

**After launching your instance:**

1. **Go to EC2 Console → Security Groups**
2. **Select "default" security group** (or the one you used)
3. **Click "Edit inbound rules"**
4. **Click "Add rule"** and add:
   - **SSH (22)**: 
     - Type: SSH
     - Source: Your IP (e.g., `203.0.113.45/32`)
   - **Custom TCP (8000)**: 
     - Type: Custom TCP
     - Port: 8000
     - Source: Your IP
   - **Custom TCP (8501)**: 
     - Type: Custom TCP
     - Port: 8501
     - Source: Your IP
5. **Click "Save rules"**

**Find your IPv4 address:**
```bash
# Use -4 to force IPv4 (AWS security groups need IPv4, not IPv6)
curl -4 ifconfig.me
# or
curl -4 https://api.ipify.org
```

> **Tip**: You can also add these rules during instance creation by clicking "Edit" next to the security group selection.

### Step 2: Connect to EC2 Instance

```bash
# From your local machine
# Make sure your key has correct permissions (required for security)
chmod 400 your-key.pem  # Linux/Mac

# Connect to instance
ssh -i your-key.pem ec2-user@your-ec2-public-ip

# For Ubuntu AMI, use:
ssh -i your-key.pem ubuntu@your-ec2-public-ip
```

> **Note**: Both RSA and ED25519 keys work the same way with SSH. The connection command is identical.

### Step 3: Install Docker and Docker Compose

**For Amazon Linux 2023:**
```bash
# Update system
sudo yum update -y

# Install Docker
sudo yum install docker -y
sudo service docker start
sudo usermod -a -G docker ec2-user

# Install Docker Compose (V2 plugin)
sudo yum install docker-compose-plugin -y

# Log out and back in for group changes
exit
# SSH back in
ssh -i your-key.pem ec2-user@your-ec2-public-ip

# Verify installation
docker --version
docker compose version
```

**For Ubuntu 22.04:**
```bash
# Update system
sudo apt-get update -y

# Install Docker
sudo apt-get install docker.io -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ubuntu

# Install Docker Compose (V2 plugin)
sudo apt-get install docker-compose-plugin -y

# Log out and back in
exit
# SSH back in
ssh -i your-key.pem ubuntu@your-ec2-public-ip

# Verify installation
docker --version
docker compose version
```

### Step 4: Transfer Project Files

**Option A: Using Git (Recommended)**
```bash
# On EC2 instance
cd ~
git clone https://github.com/your-username/ai-research-assistant.git
cd ai-research-assistant
```

**Option B: Using SCP**
```bash
# From your local machine
scp -i your-key.pem -r . ec2-user@your-ec2-public-ip:/home/ec2-user/ai-research-assistant/
```

**Option C: Using rsync (excludes .git, node_modules, etc.)**
```bash
# From your local machine
rsync -avz --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' \
  -e "ssh -i your-key.pem" \
  ./ ec2-user@your-ec2-public-ip:/home/ec2-user/ai-research-assistant/
```

### Step 5: Configure Environment Variables

```bash
# On EC2 instance
cd ~/ai-research-assistant

# Create .env file from example
cp .env.example .env

# Edit .env file
nano .env  # or use vi/vim
```

**Required environment variables** (add to `.env`):
```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Pinecone
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=your-index-name

# AWS
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET_NAME=aira-project-bucket
AWS_REGION=us-east-1

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# Database
TASK_DB_PATH=/app/data/tasks.db
```

**Save and exit** (in nano: `Ctrl+X`, then `Y`, then `Enter`)

### Step 6: Build and Start Services

```bash
# Build Docker images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start services in background
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

**Expected output:**
```
NAME                    STATUS          PORTS
ai-research-api         Up 2 minutes    0.0.0.0:8000->8000/tcp
ai-research-streamlit   Up 2 minutes    0.0.0.0:8501->8501/tcp
```

### Step 7: Verify Deployment

```bash
# Test API health
curl http://localhost:8000/health

# Test Streamlit health
curl http://localhost:8501/_stcore/health

# Check from outside (use your EC2 public IP)
curl http://YOUR-EC2-PUBLIC-IP:8000/health
```

**Access your services:**
- **API**: `http://YOUR-EC2-PUBLIC-IP:8000`
- **API Docs**: `http://YOUR-EC2-PUBLIC-IP:8000/docs`
- **Streamlit**: `http://YOUR-EC2-PUBLIC-IP:8501`

---

## Optional: Set Up Nginx Reverse Proxy

For production, set up Nginx to serve on ports 80/443 with SSL.

### Install Nginx

**Amazon Linux:**
```bash
sudo yum install nginx -y
sudo systemctl start nginx
sudo systemctl enable nginx
```

**Ubuntu:**
```bash
sudo apt-get install nginx -y
sudo systemctl start nginx
sudo systemctl enable nginx
```

### Configure Nginx

```bash
sudo nano /etc/nginx/conf.d/ai-research.conf
```

**Add this configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;  # or your EC2 public IP

    # API endpoints
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API docs
    location /docs {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Streamlit app
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Test and reload Nginx:**
```bash
sudo nginx -t
sudo systemctl reload nginx
```

**Now access via:**
- `http://YOUR-EC2-PUBLIC-IP` (Streamlit)
- `http://YOUR-EC2-PUBLIC-IP/api` (API)
- `http://YOUR-EC2-PUBLIC-IP/docs` (API docs)

---

## SSL/HTTPS Setup (Optional but Recommended)

### Using Let's Encrypt (Certbot)

```bash
# Install Certbot
sudo yum install certbot python3-certbot-nginx -y  # Amazon Linux
# or
sudo apt-get install certbot python3-certbot-nginx -y  # Ubuntu

# Get SSL certificate (replace with your domain)
sudo certbot --nginx -d your-domain.com

# Auto-renewal is set up automatically
```

---

## Common Operations

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f streamlit

# Last 100 lines
docker compose logs --tail=100 api
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart api
docker compose restart streamlit
```

### Stop Services

```bash
docker compose down
```

### Update Application

```bash
# Pull latest code
git pull

# Rebuild and restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Or rebuild specific service
docker compose -f docker-compose.yml -f docker-compose.prod.yml build api
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d api
```

### Backup Data

```bash
# Backup database and logs
cd ~/ai-research-assistant
tar -czf backup-$(date +%Y%m%d).tar.gz data/ logs/

# Copy to S3 (optional)
aws s3 cp backup-*.tar.gz s3://your-backup-bucket/
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker compose logs

# Check if ports are in use
sudo netstat -tulpn | grep -E '8000|8501'

# Check Docker status
docker ps -a
docker compose ps
```

### API Not Accessible

```bash
# Check API health
curl http://localhost:8000/health

# Check if container is running
docker compose ps api

# Check API logs
docker compose logs api

# Check security group allows port 8000
# AWS Console → EC2 → Security Groups → Inbound rules
```

**Common Issues:**
- **Security group blocking**: Verify your IP is in the allowed list
- **Wrong IP address**: Your IP may have changed (dynamic IP)
  ```bash
  # Find your current IPv4 address (use -4 for IPv4)
  curl -4 ifconfig.me
  # Update security group rule with new IP
  ```
- **Instance firewall**: Check if instance-level firewall is blocking ports

### Streamlit Can't Connect to API

```bash
# Verify API_BASE_URL in docker-compose.yml
# Should be: http://api:8000 (internal Docker network)

# Test connectivity from Streamlit container
docker compose exec streamlit curl http://api:8000/health
```

### Out of Memory

```bash
# Check resource usage
docker stats

# Adjust limits in docker-compose.prod.yml
# Or use larger EC2 instance
```

### Permission Denied Errors

```bash
# Fix Docker permissions
sudo usermod -aG docker $USER
# Log out and back in
```

### Environment Variables Not Loading

```bash
# Verify .env file exists
ls -la .env

# Check if variables are loaded
docker compose exec api env | grep OPENAI

# Restart services after .env changes
docker compose down
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### VPC/Networking Issues

```bash
# Check if instance has public IP
# In EC2 Console → Instances → Select your instance → Check "Public IPv4 address"

# If no public IP, you may need to:
# 1. Stop instance
# 2. Actions → Networking → Change subnet → Select subnet with auto-assign public IP enabled
# 3. Start instance

# Verify default VPC exists
# AWS Console → VPC → Your VPCs → Should see "default" VPC

# Check security group rules
# EC2 Console → Security Groups → Select your security group → Inbound rules
```

### No Default VPC Available

**If you deleted your default VPC**, see the section above: **"I Deleted My Default VPC - How Do I Create a New One?"**

**Quick fix:**
1. AWS Console → VPC Dashboard
2. Actions → "Create Default VPC"
3. Select region → Create

This recreates everything automatically (subnets, internet gateway, route tables).

### Can't Access Instance from Internet

**Common causes:**
1. **No public IP**: Instance needs a public IP to be accessible
2. **Security group blocking**: Check inbound rules allow your IP
3. **Instance in private subnet**: Use public subnet or enable NAT gateway
4. **Default VPC deleted**: Create new default VPC or use custom VPC

**Solutions:**
- Ensure "Auto-assign Public IP" is enabled when launching
- Verify security group allows your IP address
- Check route table has internet gateway route (default VPC has this automatically)

### SSH Key Pair Issues

**"Permission denied (publickey)" error:**
```bash
# Check key file permissions (must be 400 or 600)
chmod 400 your-key.pem  # Linux/Mac

# Verify you're using the correct key
# The key name in EC2 console must match the file you're using

# Check you're using the correct username
# Amazon Linux: ec2-user
# Ubuntu: ubuntu
# Debian: admin
# CentOS: centos
```

**"Key format not supported" error:**
- Make sure you downloaded `.pem` format (not `.ppk`)
- If you have `.ppk` (PuTTY format), convert it:
  ```bash
  # Using PuTTYgen (Windows) or:
  puttygen your-key.ppk -O private-openssh -o your-key.pem
  ```

**RSA vs ED25519:**
- **ED25519** (recommended): Modern, secure, faster, smaller keys (256 bits)
- **RSA**: Traditional, widely compatible, larger keys (2048+ bits recommended)
- Both work identically with EC2 - choose based on your preference
- AWS supports both types fully

### Security Group Access Issues

**"Connection timeout" or "Connection refused":**
```bash
# 1. Verify your current IPv4 address (use -4 for IPv4)
curl -4 ifconfig.me

# 2. Check security group rules in AWS Console
# EC2 → Security Groups → Select your security group → Inbound rules
# Make sure your IP is listed (not just 0.0.0.0/0)

# 3. If your IP changed (dynamic IP), update security group:
# AWS Console → Security Groups → Edit inbound rules
# Update the source IP for the affected port

# 4. For dynamic IPs, consider:
# - Using a VPN with static IP
# - Using AWS Systems Manager Session Manager (no SSH needed)
# - Using a small CIDR range if you know your IP range
```

**Best Practices:**
- ✅ **Always restrict SSH (22) to your IP only** - never use 0.0.0.0/0
- ✅ **Use specific IPs for API/Streamlit ports** in development
- ✅ **Use Nginx reverse proxy** for production (only open 80/443 publicly)
- ✅ **Regularly review security group rules** and remove unused rules
- ✅ **Use AWS Systems Manager Session Manager** as alternative to SSH (no port 22 needed)

---

## Production Best Practices

1. **Security Groups**: 
   - ✅ **Restrict SSH (22) to your IP only** - never use 0.0.0.0/0
   - ✅ Use specific IP addresses instead of 0.0.0.0/0 for all ports
   - ✅ Only open ports 80/443 publicly if using HTTPS with SSL
   - ✅ Consider AWS Systems Manager Session Manager instead of SSH
2. **Use HTTPS**: Set up SSL/TLS with Let's Encrypt
3. **Monitor Resources**: Use CloudWatch or similar
4. **Backup Regularly**: Automate database backups to S3
5. **Log Rotation**: Configure log rotation in docker-compose.prod.yml
6. **Security Updates**: Keep Docker and images updated
7. **Resource Limits**: Set appropriate CPU/memory limits (already in docker-compose.prod.yml)
8. **Health Checks**: Monitor health endpoints
9. **Load Balancing**: Use ALB for multiple instances
10. **Auto-scaling**: Set up auto-scaling groups for high traffic
11. **Secrets Management**: Consider AWS Secrets Manager instead of .env file
12. **Network Security**: Use VPC security groups + instance-level firewalls for defense in depth

---

## Cost Optimization

- **Instance Types**: Start with t3.medium, scale up as needed
- **Spot Instances**: Use EC2 Spot Instances for development/testing
- **Reserved Instances**: For production, consider Reserved Instances
- **Auto-scaling**: Scale down during low-traffic periods
- **CloudWatch**: Monitor and optimize resource usage

---

## Next Steps

1. ✅ Deploy to EC2
2. 📋 Set up domain name and DNS
3. 📋 Configure SSL/HTTPS
4. 📋 Set up monitoring (CloudWatch)
5. 📋 Configure automated backups
6. 📋 Set up CI/CD pipeline
7. 📋 Load testing and optimization

---

## Quick Reference

```bash
# Start services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Stop services
docker compose down

# View logs
docker compose logs -f

# Restart services
docker compose restart

# Update and rebuild
git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Check status
docker compose ps
curl http://localhost:8000/health
```

---

## Support

For issues or questions:
1. Check the [DOCKER.md](DOCKER.md) for detailed Docker instructions
2. Review [README.md](README.md) for general setup
3. Check logs: `docker compose logs -f`
4. Verify environment variables are set correctly
