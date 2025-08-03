#!/usr/bin/env python3
"""
GitHub Star Organizer

Automated system to organize starred repositories into categorized GitHub lists.
This script analyzes repositories based on their topics, descriptions, languages,
and README content to automatically categorize them.

Author: Sagar Gupta
GitHub: https://github.com/Sagargupta16
"""

import os
import sys
import json
import logging
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import yaml

try:
    from github import Github
    from github.Repository import Repository
    from github.GithubException import GithubException
    import requests
except ImportError as e:
    print(f"Error: Required packages not installed. Please run: pip install -r requirements.txt")
    print(f"Missing package: {e}")
    sys.exit(1)


class StarOrganizer:
    """Main class for organizing starred repositories into categories."""
    
    def __init__(self, github_token: str, config_path: str = "config/categories.yml"):
        """
        Initialize the StarOrganizer.
        
        Args:
            github_token: GitHub personal access token
            config_path: Path to the categories configuration file
        """
        self.github = Github(github_token)
        self.user = self.github.get_user()
        self.config_path = config_path
        self.categories = {}
        self.min_confidence = 0.3
        self.category_priority = []
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('star_organizer.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        self.load_config()
    
    def load_config(self) -> None:
        """Load categories configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                self.categories = config.get('categories', {})
                self.min_confidence = config.get('min_confidence', 0.3)
                self.category_priority = config.get('category_priority', [])
                self.default_category = config.get('default_category', 'Development & Programming')
                
            self.logger.info(f"Loaded {len(self.categories)} categories from {self.config_path}")
            
        except FileNotFoundError:
            self.logger.error(f"Configuration file not found: {self.config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing YAML configuration: {e}")
            sys.exit(1)
    
    def get_starred_repositories(self) -> List[Repository]:
        """Fetch all starred repositories for the authenticated user."""
        try:
            starred_repos = list(self.user.get_starred())
            self.logger.info(f"Found {len(starred_repos)} starred repositories")
            return starred_repos
        except GithubException as e:
            self.logger.error(f"Error fetching starred repositories: {e}")
            return []
    
    def analyze_repository(self, repo: Repository) -> Dict[str, any]:
        """
        Analyze a repository to extract metadata for categorization.
        
        Args:
            repo: GitHub Repository object
            
        Returns:
            Dictionary containing repository analysis data
        """
        try:
            # Basic repository information
            analysis = {
                'name': repo.name,
                'full_name': repo.full_name,
                'description': repo.description or '',
                'topics': repo.get_topics(),
                'language': repo.language,
                'languages': {},
                'stars': repo.stargazers_count,
                'forks': repo.forks_count,
                'readme_content': '',
                'url': repo.html_url
            }
            
            # Get language statistics
            try:
                analysis['languages'] = repo.get_languages()
            except GithubException:
                pass
            
            # Try to get README content (first 2000 characters)
            try:
                readme = repo.get_readme()
                content = readme.decoded_content.decode('utf-8')
                analysis['readme_content'] = content[:2000].lower()
            except GithubException:
                pass
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Error analyzing repository {repo.full_name}: {e}")
            return {
                'name': repo.name,
                'full_name': repo.full_name,
                'description': '',
                'topics': [],
                'language': None,
                'languages': {},
                'stars': 0,
                'forks': 0,
                'readme_content': '',
                'url': repo.html_url
            }
    
    def calculate_category_score(self, repo_analysis: Dict[str, any], category_name: str, category_config: Dict[str, any]) -> float:
        """
        Calculate confidence score for a repository belonging to a specific category.
        
        Args:
            repo_analysis: Repository analysis data
            category_name: Name of the category
            category_config: Category configuration
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        score = 0.0
        total_weight = 0.0
        
        # Weight for different matching criteria
        weights = {
            'topics': 0.4,
            'keywords': 0.3,
            'languages': 0.2,
            'readme': 0.1
        }
        
        # Check topics match
        repo_topics = [topic.lower() for topic in repo_analysis.get('topics', [])]
        category_topics = [topic.lower() for topic in category_config.get('topics', [])]
        
        if category_topics:
            topic_matches = len(set(repo_topics) & set(category_topics))
            topic_score = min(topic_matches / len(category_topics), 1.0)
            score += topic_score * weights['topics']
            total_weight += weights['topics']
        
        # Check keyword matches in description and README
        keywords = [kw.lower() for kw in category_config.get('keywords', [])]
        if keywords:
            text_to_search = (
                repo_analysis.get('description', '').lower() + ' ' +
                repo_analysis.get('readme_content', '').lower()
            )
            
            keyword_matches = sum(1 for kw in keywords if kw in text_to_search)
            keyword_score = min(keyword_matches / len(keywords), 1.0)
            score += keyword_score * weights['keywords']
            total_weight += weights['keywords']
        
        # Check language matches
        category_languages = [lang.lower() for lang in category_config.get('languages', [])]
        if category_languages:
            repo_language = repo_analysis.get('language', '').lower() if repo_analysis.get('language') else ''
            repo_languages = [lang.lower() for lang in repo_analysis.get('languages', {}).keys()]
            
            language_match = (
                repo_language in category_languages or
                any(lang in category_languages for lang in repo_languages)
            )
            
            if language_match:
                score += weights['languages']
            total_weight += weights['languages']
        
        # Normalize score
        if total_weight > 0:
            score = score / total_weight
        
        return score
    
    def categorize_repository(self, repo_analysis: Dict[str, any]) -> Tuple[str, float]:
        """
        Categorize a repository based on its analysis.
        
        Args:
            repo_analysis: Repository analysis data
            
        Returns:
            Tuple of (category_name, confidence_score)
        """
        best_category = self.default_category
        best_score = 0.0
        
        # Calculate scores for all categories
        category_scores = {}
        for category_name, category_config in self.categories.items():
            score = self.calculate_category_score(repo_analysis, category_name, category_config)
            category_scores[category_name] = score
        
        # Find the best category with priority consideration
        for category in self.category_priority:
            if category in category_scores and category_scores[category] >= self.min_confidence:
                if category_scores[category] > best_score:
                    best_category = category
                    best_score = category_scores[category]
        
        # If no priority category found, use the highest scoring category
        if best_score < self.min_confidence:
            for category_name, score in category_scores.items():
                if score > best_score:
                    best_category = category_name
                    best_score = score
        
        return best_category, best_score
    
    def create_github_list(self, list_name: str, description: str = "") -> bool:
        """
        Create a GitHub list (currently using a simple approach).
        Note: GitHub Lists API is limited, so we'll simulate this with a JSON file for now.
        
        Args:
            list_name: Name of the list to create
            description: Description of the list
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create lists directory if it doesn't exist
            os.makedirs('lists', exist_ok=True)
            
            list_file = f"lists/{list_name.lower().replace(' ', '_').replace('&', 'and')}.json"
            
            if not os.path.exists(list_file):
                list_data = {
                    'name': list_name,
                    'description': description,
                    'created_at': datetime.now().isoformat(),
                    'repositories': []
                }
                
                with open(list_file, 'w', encoding='utf-8') as f:
                    json.dump(list_data, f, indent=2, ensure_ascii=False)
                
                self.logger.info(f"Created list: {list_name}")
                return True
            else:
                self.logger.info(f"List already exists: {list_name}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error creating list {list_name}: {e}")
            return False
    
    def add_repository_to_list(self, list_name: str, repo_info: Dict[str, any]) -> bool:
        """
        Add a repository to a specific list.
        
        Args:
            list_name: Name of the list
            repo_info: Repository information dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            list_file = f"lists/{list_name.lower().replace(' ', '_').replace('&', 'and')}.json"
            
            if os.path.exists(list_file):
                with open(list_file, 'r', encoding='utf-8') as f:
                    list_data = json.load(f)
                
                # Check if repository is already in the list
                existing_repos = [repo['full_name'] for repo in list_data.get('repositories', [])]
                if repo_info['full_name'] not in existing_repos:
                    list_data['repositories'].append(repo_info)
                    list_data['updated_at'] = datetime.now().isoformat()
                    
                    with open(list_file, 'w', encoding='utf-8') as f:
                        json.dump(list_data, f, indent=2, ensure_ascii=False)
                    
                    return True
                else:
                    self.logger.debug(f"Repository {repo_info['full_name']} already in list {list_name}")
                    return True
            else:
                self.logger.error(f"List file not found: {list_file}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error adding repository to list {list_name}: {e}")
            return False
    
    def organize_starred_repositories(self) -> Dict[str, List[Dict[str, any]]]:
        """
        Main method to organize all starred repositories into categories.
        
        Returns:
            Dictionary mapping category names to lists of repositories
        """
        self.logger.info("Starting repository organization process...")
        
        # Get all starred repositories
        starred_repos = self.get_starred_repositories()
        if not starred_repos:
            self.logger.warning("No starred repositories found.")
            return {}
        
        # Create lists for all categories
        for category_name, category_config in self.categories.items():
            description = category_config.get('description', '')
            self.create_github_list(category_name, description)
        
        # Organize repositories
        organized_repos = {category: [] for category in self.categories.keys()}
        categorization_summary = {}
        
        total_repos = len(starred_repos)
        for i, repo in enumerate(starred_repos, 1):
            self.logger.info(f"Processing repository {i}/{total_repos}: {repo.full_name}")
            
            try:
                # Analyze repository
                repo_analysis = self.analyze_repository(repo)
                
                # Categorize repository
                category, confidence = self.categorize_repository(repo_analysis)
                
                # Prepare repository info for storage
                repo_info = {
                    'name': repo_analysis['name'],
                    'full_name': repo_analysis['full_name'],
                    'description': repo_analysis['description'],
                    'url': repo_analysis['url'],
                    'language': repo_analysis['language'],
                    'topics': repo_analysis['topics'],
                    'stars': repo_analysis['stars'],
                    'forks': repo_analysis['forks'],
                    'categorized_at': datetime.now().isoformat(),
                    'confidence_score': confidence
                }
                
                # Add to organized repositories
                organized_repos[category].append(repo_info)
                
                # Add to GitHub list
                self.add_repository_to_list(category, repo_info)
                
                # Update summary
                if category not in categorization_summary:
                    categorization_summary[category] = 0
                categorization_summary[category] += 1
                
                self.logger.info(f"Categorized {repo.full_name} as '{category}' (confidence: {confidence:.2f})")
                
            except Exception as e:
                self.logger.error(f"Error processing repository {repo.full_name}: {e}")
                continue
        
        # Log summary
        self.logger.info("Repository organization completed!")
        self.logger.info("Summary by category:")
        for category, count in sorted(categorization_summary.items()):
            self.logger.info(f"  {category}: {count} repositories")
        
        return organized_repos
    
    def generate_markdown_report(self, organized_repos: Dict[str, List[Dict[str, any]]]) -> str:
        """
        Generate a markdown report of the organized repositories.
        
        Args:
            organized_repos: Dictionary of categorized repositories
            
        Returns:
            Markdown content as string
        """
        report = []
        report.append("# Starred Repository Organization Report")
        report.append(f"\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\nTotal repositories organized: {sum(len(repos) for repos in organized_repos.values())}")
        report.append("\n---\n")
        
        for category_name in self.category_priority:
            if category_name in organized_repos and organized_repos[category_name]:
                repos = organized_repos[category_name]
                category_config = self.categories.get(category_name, {})
                description = category_config.get('description', '')
                
                report.append(f"## {category_name}")
                report.append(f"\n{description}")
                report.append(f"\n**Total repositories: {len(repos)}**\n")
                
                for repo in sorted(repos, key=lambda x: x['stars'], reverse=True):
                    report.append(f"- **[{repo['name']}]({repo['url']})** ⭐ {repo['stars']}")
                    if repo['description']:
                        report.append(f"  - {repo['description']}")
                    if repo['language']:
                        report.append(f"  - Language: {repo['language']}")
                    if repo['topics']:
                        topics_str = ", ".join(repo['topics'][:5])  # Show first 5 topics
                        report.append(f"  - Topics: {topics_str}")
                    report.append("")
                
                report.append("\n---\n")
        
        return "\n".join(report)
    
    def save_report(self, organized_repos: Dict[str, List[Dict[str, any]]], output_file: str = "star_organization_report.md") -> None:
        """
        Save the organization report to a file.
        
        Args:
            organized_repos: Dictionary of categorized repositories
            output_file: Output file path
        """
        try:
            report_content = self.generate_markdown_report(organized_repos)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            self.logger.info(f"Organization report saved to: {output_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving report: {e}")


def main():
    """Main function to run the star organizer."""
    # Get GitHub token from environment variable
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        print("Error: GITHUB_TOKEN environment variable is required.")
        print("Please set it with your GitHub personal access token.")
        sys.exit(1)
    
    try:
        # Initialize organizer
        organizer = StarOrganizer(github_token)
        
        # Organize repositories
        organized_repos = organizer.organize_starred_repositories()
        
        # Generate and save report
        organizer.save_report(organized_repos)
        
        print("Repository organization completed successfully!")
        print("Check the generated files:")
        print("- star_organization_report.md (summary report)")
        print("- lists/ directory (categorized repository lists)")
        print("- star_organizer.log (detailed logs)")
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()