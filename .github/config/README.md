# Profile Configuration

This folder contains centralized configuration for all profile usernames and settings.

## 📋 Purpose

Instead of updating usernames in multiple places (README, workflows, etc.), we maintain a **single source of truth** in `profiles.yml`.

## 🎯 Benefits

- ✅ **Consistency** - No more username mismatches (e.g., "SAGARGUPTA16" vs "sagargupta1610")
- ✅ **Easy Updates** - Change username once, updates everywhere
- ✅ **Automation** - GitHub Actions workflows read from this config
- ✅ **Maintainability** - All profile info in one place

## 📁 Files

### `profiles.yml`
Main configuration file containing:
- Personal information (name, email, timezone)
- Social media usernames (GitHub, LinkedIn, LeetCode, etc.)
- Platform URLs
- Badge and theme preferences
- Workflow settings

## 🔧 How It's Used

### In GitHub Actions Workflows

Workflows read values from this config:

```yaml
- name: Read profile configuration
  id: config
  run: |
    echo "leetcode_user=$(yq '.leetcode.username' .github/config/profiles.yml)" >> $GITHUB_OUTPUT

- name: Use the value
  uses: some-action@v1
  with:
    username: ${{ steps.config.outputs.leetcode_user }}
```

### Current Integrations

- **`metrics.yml`** - Reads GitHub username, LeetCode username, timezone
- **Future workflows** - Can use any value from profiles.yml

## 📝 How to Update

1. Edit `profiles.yml`
2. Commit and push changes
3. Workflows will automatically use new values on next run

## ⚠️ Important Notes

- LeetCode username: **sagargupta1610** (use consistently)
- This file is tracked in git (not sensitive data)
- Changes take effect on next workflow run
- README still needs manual updates (for now)

## 🔮 Future Enhancements

Potential improvements:
- Auto-generate parts of README from config
- Validation script to check consistency
- Template system for README generation
- CI check to prevent username mismatches

