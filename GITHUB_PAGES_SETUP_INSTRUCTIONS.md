# GitHub Pages Setup Instructions

## 🎯 Current Setup: GitHub Actions (Recommended)

EVOSEAL is configured to use **GitHub Actions** for documentation deployment, which provides the best experience.

### Step 1: Enable GitHub Pages

1. Go to your GitHub repository: `https://github.com/SHA888/EVOSEAL`
2. Click on **Settings** tab
3. Scroll down to **Pages** section in the left sidebar
4. Under **Source**, select **"GitHub Actions"**
5. Click **Save**

### Step 2: Verify Workflow

The workflow is already configured in `.github/workflows/docs.yml`. It will:
- Trigger on pushes to main branch
- Build MkDocs documentation
- Deploy to `gh-pages` branch automatically

### Step 3: First Deployment

Push your current changes to trigger the first build:
```bash
git push origin main
```

### Step 4: Check Deployment

1. Go to **Actions** tab in your GitHub repo
2. You should see a "Deploy Documentation" workflow running
3. Once complete, your docs will be available at: `https://sha888.github.io/EVOSEAL/`

---

## 🔄 Alternative: Deploy from docs/ folder directly

If you prefer to deploy directly from the `docs/` folder (simpler but less features):

### Step 1: Enable GitHub Pages

1. Go to **Settings** → **Pages**
2. Under **Source**, select **"Deploy from a branch"**
3. Select **Branch**: `main`
4. Select **Folder**: `/ (root)` or `/docs`
5. Click **Save**

### Step 2: Prepare docs/ for direct serving

We would need to:
1. Convert MkDocs files to plain HTML/Jekyll
2. Add `index.html` in docs/ folder
3. Remove MkDocs-specific features

---

## 🎯 Recommendation

**Use GitHub Actions approach** because it provides:
- ✅ Professional Material Design theme
- ✅ Search functionality
- ✅ Mobile responsive design
- ✅ Automatic table of contents
- ✅ Code syntax highlighting
- ✅ Dark/light mode toggle
- ✅ Git integration (last modified dates)

The direct `docs/` folder approach would lose all these features and just show basic markdown.

---

## 🚀 Quick Setup (GitHub Actions)

1. **Repository Settings** → **Pages** → **Source** → **"GitHub Actions"**
2. **Push to main branch** to trigger deployment
3. **Visit**: `https://sha888.github.io/EVOSEAL/`

That's it! The documentation will automatically build and deploy with the professional theme.
