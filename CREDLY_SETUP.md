# Credly Badges Integration

This repository now uses the `pemtajo/badge-readme` GitHub Action to automatically fetch and display Credly badges in the README.md file.

## ✨ What's Working

✅ **Automated badge fetching** via GitHub Actions  
✅ **Clean badge display** with proper sizing  
✅ **Daily automatic updates** at 2 AM UTC  
✅ **Manual trigger** option via GitHub Actions  
✅ **Proper comment markers** for badge insertion  

## 🏆 Features

- **Automatic Updates**: Badges are fetched daily from your Credly profile
- **Clean Display**: Badges are displayed in an 80x80 pixel format
- **Responsive Layout**: Works well on all devices
- **Direct Links**: Each badge links to your Credly verification page

## 🚀 How It Works

1. **GitHub Action runs** daily at 2 AM UTC (or manually triggered)
2. **Fetches your latest badges** from Credly profile: `sagar-gupta.f8eb96cc`
3. **Updates README.md** between the comment markers:
   ```
   <!--START_SECTION:badges-->
   <!--END_SECTION:badges-->
   ```
4. **Commits changes** automatically to the repository

## 🔧 Configuration

The action is configured in `.github/workflows/credly-badges.yml` with:
- **Credly Username**: `sagar-gupta.f8eb96cc`
- **Number of Badges**: `10` (shows last 10 badges)
- **Schedule**: Daily at 2 AM UTC
- **Manual Trigger**: Available via GitHub Actions tab

## 📋 Files

- `.github/workflows/credly-badges.yml` - Main GitHub Action workflow  
- `README.md` - Updated with badge comment markers  
- `CREDLY_SETUP.md` - This documentation file

## 🎯 Next Steps

1. **Test the workflow**: Go to Actions → "Update Credly Badges" → "Run workflow"
2. **Check results**: Your badges should appear in the README.md
3. **Verify daily updates**: The action will run automatically every day

## 🔗 Resources

- [pemtajo/badge-readme](https://github.com/pemtajo/badge-readme) - The GitHub Action used
- [Your Credly Profile](https://www.credly.com/users/sagar-gupta.f8eb96cc/badges) - Your badge source
- [GitHub Actions](https://github.com/Sagargupta16/Sagargupta16/actions) - View action runs

---

*Credly badges will automatically appear in your README.md within 24 hours or when manually triggered!* 🏆
