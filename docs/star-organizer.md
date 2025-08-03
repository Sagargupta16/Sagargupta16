# GitHub Star Organization System

An automated system to organize all starred repositories on GitHub into proper categorized lists for better discoverability and management.

## 🌟 Overview

This system automatically analyzes your starred repositories and organizes them into predefined categories based on:
- Repository topics/tags
- README content analysis
- Programming languages used
- Repository description keywords

## 📋 Features

- **Automated Categorization**: Intelligent analysis of repository metadata
- **Multiple Categories**: 11 predefined categories covering various domains
- **Bulk Organization**: Efficient processing of large numbers of starred repositories
- **Maintenance Automation**: Scheduled re-categorization and updates
- **Detailed Reporting**: Comprehensive reports with categorization statistics
- **Confidence Scoring**: Each categorization includes a confidence score
- **Error Handling**: Robust error handling and logging
- **GitHub Actions Integration**: Fully automated with GitHub workflows

## 🗂️ Categories

The system organizes repositories into the following categories:

1. **Development & Programming** - General programming tools, frameworks, and development resources
2. **ML & AI** - Machine Learning, Artificial Intelligence, and Data Science projects
3. **Tools & Utilities** - Development tools, utilities, and productivity software
4. **DevOps & Cloud** - DevOps tools, cloud infrastructure, and deployment resources
5. **Learning & Education** - Educational resources, tutorials, and learning materials
6. **Games & Entertainment** - Game development, entertainment projects, and fun applications
7. **Open Source Projects** - Notable open source projects and community-driven initiatives
8. **Portfolio & Showcase** - Portfolio projects, personal websites, and showcase repositories
9. **System Administration** - System administration tools, scripts, and configurations
10. **Mobile & Cross-Platform** - Mobile development and cross-platform applications
11. **Design & Frontend** - UI/UX design, frontend frameworks, and web design resources

## 🚀 Quick Start

### Prerequisites

1. **GitHub Personal Access Token**: Create a token with `repo` and `read:user` scopes
2. **Python 3.9+**: Required for running the organizer script
3. **Dependencies**: Install required Python packages

### Setup

1. **Clone the repository** (if not already done):
   ```bash
   git clone https://github.com/Sagargupta16/Sagargupta16.git
   cd Sagargupta16
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   export GITHUB_TOKEN="your_github_personal_access_token"
   ```

4. **Run the organizer**:
   ```bash
   cd scripts
   python star_organizer.py
   ```

### Automated Execution

The system runs automatically every Sunday at 2 AM UTC via GitHub Actions. You can also trigger it manually:

1. Go to the **Actions** tab in your repository
2. Select **"Organize Starred Repositories"** workflow
3. Click **"Run workflow"**

## 📁 Output Files

After running, the system generates:

- **`lists/`** - Directory containing JSON files for each category
- **`docs/star_organization_report.md`** - Comprehensive markdown report
- **`star_organizer.log`** - Detailed execution logs

### List File Structure

Each category list is stored as a JSON file:

```json
{
  "name": "Development & Programming",
  "description": "General programming tools, frameworks, and development resources",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00",
  "repositories": [
    {
      "name": "repo-name",
      "full_name": "owner/repo-name",
      "description": "Repository description",
      "url": "https://github.com/owner/repo-name",
      "language": "Python",
      "topics": ["python", "library"],
      "stars": 1000,
      "forks": 100,
      "categorized_at": "2024-01-01T00:00:00",
      "confidence_score": 0.85
    }
  ]
}
```

## ⚙️ Configuration

### Categories Configuration

Edit `config/categories.yml` to customize:

- **Categories**: Add, remove, or modify categories
- **Keywords**: Update keyword lists for better matching
- **Topics**: Modify topic-based matching criteria
- **Languages**: Adjust programming language associations
- **Priority**: Set category priority for tie-breaking
- **Confidence Threshold**: Adjust minimum confidence score

### Example Category Configuration

```yaml
categories:
  "My Custom Category":
    description: "Description of the custom category"
    keywords:
      - "keyword1"
      - "keyword2"
    topics:
      - "topic1"
      - "topic2"
    languages:
      - "Python"
      - "JavaScript"
```

## 🔄 How It Works

### 1. Repository Analysis

For each starred repository, the system analyzes:
- **Basic metadata**: Name, description, language, topics
- **Language statistics**: All languages used in the repository
- **README content**: First 2000 characters for keyword analysis
- **Repository metrics**: Stars, forks, activity

### 2. Categorization Algorithm

The algorithm calculates confidence scores based on:
- **Topics matching** (40% weight): Direct topic/tag matches
- **Keyword matching** (30% weight): Keywords in description and README
- **Language matching** (20% weight): Primary and secondary languages
- **README analysis** (10% weight): Content analysis for context

### 3. Category Assignment

- Repositories are assigned to the highest-scoring category
- Minimum confidence threshold prevents low-quality assignments
- Priority system handles ties between categories
- Default category for repositories that don't match any criteria

## 🛠️ Advanced Usage

### Manual Execution with Options

```bash
# Set custom configuration path
export CONFIG_PATH="path/to/custom/categories.yml"

# Run with debug logging
export LOG_LEVEL="DEBUG"

# Run the organizer
python star_organizer.py
```

### Custom Categories

Create your own categorization rules by modifying `config/categories.yml`:

1. **Add new categories** with specific criteria
2. **Adjust keyword lists** for better matching
3. **Set category priorities** for your preferences
4. **Modify confidence thresholds** for stricter/looser categorization

### Integration with Other Tools

The generated JSON files can be used with other tools:
- **GitHub CLI**: Script repository operations
- **Data analysis**: Process with pandas, R, or other tools
- **Visualization**: Create charts and graphs
- **APIs**: Build web interfaces or mobile apps

## 📊 Monitoring and Maintenance

### Logs and Debugging

- **Console output**: Real-time progress and summary
- **Log file**: Detailed execution logs in `star_organizer.log`
- **GitHub Actions**: Workflow execution logs and summaries

### Performance Considerations

- **API rate limits**: Respects GitHub API rate limits
- **Large repositories**: Handles repositories with many files efficiently
- **README analysis**: Limits content analysis to first 2000 characters
- **Error recovery**: Continues processing if individual repositories fail

### Regular Maintenance

The system automatically:
- **Re-categorizes** repositories that may have changed
- **Updates** repository metadata (stars, topics, etc.)
- **Generates** fresh reports with current data
- **Maintains** historical data in version control

## 🔧 Troubleshooting

### Common Issues

1. **API Rate Limits**:
   - Solution: Use authenticated requests with personal access token
   - The system automatically handles rate limiting

2. **Missing Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Token Permissions**:
   - Ensure token has `repo` and `read:user` scopes
   - For organization repositories, additional permissions may be needed

4. **Configuration Errors**:
   - Validate YAML syntax in `config/categories.yml`
   - Check category names and structure

### Debug Mode

Enable detailed logging:
```bash
export LOG_LEVEL="DEBUG"
python star_organizer.py
```

### GitHub Actions Debugging

Check the Actions tab for:
- Workflow execution logs
- Error messages and stack traces
- Artifact downloads for manual inspection

## 🤝 Contributing

### Adding New Categories

1. Edit `config/categories.yml`
2. Add keywords, topics, and languages for the new category
3. Test with sample repositories
4. Update documentation

### Improving Categorization

1. Analyze misclassified repositories
2. Adjust keyword lists and topics
3. Modify confidence thresholds
4. Test changes with your starred repositories

### Code Contributions

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📈 Analytics and Reporting

### Report Features

The generated markdown report includes:
- **Summary statistics** by category
- **Repository details** with metadata
- **Confidence scores** for each categorization
- **Sorting** by popularity (stars)
- **Topics and languages** for each repository

### Custom Analytics

Use the JSON files for custom analysis:
```python
import json

# Load category data
with open('lists/development_and_programming.json', 'r') as f:
    dev_repos = json.load(f)

# Analyze language distribution
languages = {}
for repo in dev_repos['repositories']:
    lang = repo.get('language')
    if lang:
        languages[lang] = languages.get(lang, 0) + 1

print(languages)
```

## 🔒 Security and Privacy

### Token Security

- **Never commit** tokens to version control
- **Use environment variables** for token storage
- **Scope tokens** minimally (only required permissions)
- **Rotate tokens** regularly

### Data Privacy

- **Public repositories only**: Only analyzes public starred repositories
- **No sensitive data**: Doesn't access private repository content
- **Metadata only**: Only uses publicly available metadata
- **Local processing**: Analysis happens in your environment

## 📚 API Reference

### StarOrganizer Class

Main class for repository organization:

```python
from star_organizer import StarOrganizer

# Initialize
organizer = StarOrganizer(github_token, config_path)

# Organize repositories
organized_repos = organizer.organize_starred_repositories()

# Generate report
organizer.save_report(organized_repos)
```

### Key Methods

- `get_starred_repositories()`: Fetch all starred repositories
- `analyze_repository(repo)`: Analyze single repository
- `categorize_repository(analysis)`: Categorize based on analysis
- `organize_starred_repositories()`: Main organization method
- `generate_markdown_report()`: Create formatted report

## 🚀 Future Enhancements

### Planned Features

1. **GitHub Lists Integration**: Direct integration with GitHub Lists API when available
2. **Machine Learning**: ML-based categorization for improved accuracy
3. **Custom Rules**: User-defined categorization rules
4. **Web Interface**: Browser-based configuration and monitoring
5. **Notifications**: Email/Slack notifications for organization updates
6. **Collaborative Features**: Shared categorization rules and categories

### Roadmap

- **v2.0**: Enhanced ML-based categorization
- **v2.1**: Web interface for configuration
- **v2.2**: Advanced analytics and insights
- **v3.0**: Multi-user and collaborative features

## 📄 License

This project is part of the personal profile repository. Feel free to use and adapt the code for your own star organization needs.

## 🙋‍♂️ Support

For questions, issues, or suggestions:

1. **GitHub Issues**: Open an issue in this repository
2. **Discussions**: Use GitHub Discussions for general questions
3. **Email**: Contact [sg85207@gmail.com](mailto:sg85207@gmail.com)
4. **LinkedIn**: Connect on [LinkedIn](https://www.linkedin.com/in/sagar16gupta)

---

**Happy organizing! 🌟** Keep your starred repositories clean and discoverable with automated categorization.