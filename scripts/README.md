# Credly Badges Integration

This directory contains scripts to automatically fetch and display Credly badges in your GitHub profile README.

## Features

- ✅ Automatically fetches all public badges from your Credly profile
- ✅ Generates a beautiful markdown display with badge images
- ✅ Includes detailed badge information (issuer, date, skills)
- ✅ Daily automatic updates via GitHub Actions
- ✅ Responsive grid layout for badges
- ✅ Fallback methods for different Credly profile configurations

## Files

- `fetch-credly-badges.js` - Main script to fetch badges from Credly API
- `test-credly-fetch.js` - Test script to verify functionality
- `../badges/` - Output directory for generated badge files
- `../.github/workflows/credly-badges.yml` - GitHub Actions workflow

## Setup

### 1. Configure Your Credly Username

The script is currently configured to use `sagar-gupta.f8eb96cc` as the Credly username. To change this:

1. Edit `fetch-credly-badges.js` and update the `CREDLY_USERNAME` constant
2. Or set the `CREDLY_USERNAME` environment variable

### 2. Make Sure Your Credly Profile is Public

For the script to work, your Credly profile must be public:

1. Go to your [Credly profile settings](https://www.credly.com/settings)
2. Ensure your profile visibility is set to "Public"
3. Make sure your badges are set to be publicly visible

### 3. Test the Script Locally (Optional)

```bash
# Install dependencies (if any)
npm install

# Test the badge fetching
npm run test-badges

# Or run directly
node scripts/test-credly-fetch.js
```

### 4. Enable GitHub Actions

The workflow is already set up and will run:
- Daily at 6 AM UTC
- Whenever you push changes to the script files
- Manually via the "Actions" tab in your repository

## How It Works

1. **Fetching**: The script connects to Credly's public API to fetch your badges
2. **Processing**: Badge data is cleaned and formatted
3. **Generation**: A markdown file is created with your badges
4. **Integration**: The README.md is automatically updated with your badges
5. **Automation**: GitHub Actions runs this process daily

## Output Format

The script generates:

### Visual Badge Display
- Grid layout showing badge images
- Clickable badges linking to credential details
- Responsive design that works on all devices

### Detailed Information Table
- Badge names and descriptions
- Issuing organizations
- Issue dates
- Associated skills

## Troubleshooting

### No Badges Found
- Check if your Credly profile is public
- Verify your username is correct
- Ensure you have public badges on your profile

### API Errors
- The script includes fallback methods for different Credly configurations
- Check GitHub Actions logs for detailed error messages

### README Not Updating
- Ensure the `<!-- CREDLY-BADGES-START -->` and `<!-- CREDLY-BADGES-END -->` markers exist in your README
- Check that the GitHub Actions workflow has write permissions

## Customization

### Badge Display
Edit the `generateBadgesMarkdown` function in `fetch-credly-badges.js` to customize:
- Number of badges per row
- Badge image sizes
- Layout and styling

### Update Frequency
Modify the cron schedule in `.github/workflows/credly-badges.yml`:
```yaml
schedule:
  - cron: "0 6 * * *"  # Daily at 6 AM UTC
```

### Badge Filtering
Add filtering logic in the `fetchCredlyBadges` function to:
- Show only recent badges
- Filter by specific issuers
- Sort by different criteria

## Example Output

The script will add a section like this to your README:

```markdown
## 🏆 Credly Certificates & Badges

<div align="center">

<a href="https://credly.com/badges/..." target="_blank">
  <img src="https://images.credly.com/..." alt="Badge Name" width="120" height="120" />
</a>
<!-- More badges... -->

</div>

<details>
<summary><h3>📋 Badge Details</h3></summary>

| Badge | Issuer | Issued Date | Skills |
|-------|--------|-------------|--------|
| [Badge 1] | AWS | Jan 15, 2024 | Cloud Computing, DevOps |
<!-- More rows... -->

</details>
```

## Privacy and Security

- Only public badge information is fetched
- No API keys or authentication required
- All data processing happens in GitHub Actions
- No personal information is stored or transmitted

## Contributing

Feel free to enhance the script by:
- Adding support for more badge providers
- Improving the visual layout
- Adding filtering and sorting options
- Enhancing error handling

---

*This integration helps showcase your professional achievements and certifications directly in your GitHub profile!* 🏆
