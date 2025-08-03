#!/usr/bin/env python3
"""
GitHub Star Organizer Demo

This script demonstrates the star organization system without requiring GitHub API access.
It shows how repositories would be categorized based on their metadata.
"""

import sys
import os
sys.path.append('scripts')

def demo_categorization():
    """Demonstrate the categorization system with example repositories."""
    
    print("🌟 GitHub Star Organization System Demo")
    print("=" * 50)
    print()
    
    # Example repositories to demonstrate categorization
    example_repos = [
        {
            'name': 'tensorflow',
            'description': 'An open source machine learning framework for everyone',
            'topics': ['machine-learning', 'deep-learning', 'neural-networks', 'python', 'tensorflow'],
            'language': 'Python',
            'stars': 185000
        },
        {
            'name': 'react',
            'description': 'A declarative, efficient, and flexible JavaScript library for building user interfaces',
            'topics': ['javascript', 'react', 'frontend', 'ui', 'web', 'library'],
            'language': 'JavaScript',
            'stars': 227000
        },
        {
            'name': 'kubernetes',
            'description': 'Production-Grade Container Scheduling and Management',
            'topics': ['kubernetes', 'docker', 'containers', 'devops', 'cloud', 'orchestration'],
            'language': 'Go',
            'stars': 109000
        },
        {
            'name': 'flutter',
            'description': 'Flutter makes it easy to build beautiful apps for mobile and beyond',
            'topics': ['flutter', 'dart', 'mobile', 'android', 'ios', 'cross-platform'],
            'language': 'Dart',
            'stars': 165000
        },
        {
            'name': 'awesome-python',
            'description': 'A curated list of awesome Python frameworks, libraries, software and resources',
            'topics': ['python', 'awesome', 'list', 'resources', 'learning', 'curated'],
            'language': 'Python',
            'stars': 218000
        },
        {
            'name': 'vs-code',
            'description': 'Visual Studio Code - The best code editor for development',
            'topics': ['editor', 'ide', 'development', 'tool', 'productivity'],
            'language': 'TypeScript',
            'stars': 150000
        }
    ]
    
    try:
        from star_organizer import StarOrganizer
        
        # Create a demo organizer
        class DemoOrganizer(StarOrganizer):
            def __init__(self):
                self.config_path = "config/categories.yml"
                self.categories = {}
                self.min_confidence = 0.2
                self.category_priority = []
                self.default_category = "Development & Programming"
                
                import logging
                logging.basicConfig(level=logging.ERROR)  # Suppress info logs
                self.logger = logging.getLogger(__name__)
                
                self.load_config()
        
        organizer = DemoOrganizer()
        
        print("🗂️ Categories Available:")
        for i, category in enumerate(organizer.categories.keys(), 1):
            print(f"   {i:2d}. {category}")
        print()
        
        print("📦 Example Repository Categorizations:")
        print("-" * 50)
        
        categorization_results = {}
        
        for repo in example_repos:
            # Prepare repository analysis format
            repo_analysis = {
                'name': repo['name'],
                'full_name': f"example/{repo['name']}",
                'description': repo['description'],
                'topics': repo['topics'],
                'language': repo['language'],
                'languages': {repo['language']: 10000},
                'stars': repo['stars'],
                'forks': repo['stars'] // 10,
                'readme_content': repo['description'].lower(),
                'url': f"https://github.com/example/{repo['name']}"
            }
            
            # Categorize
            category, confidence = organizer.categorize_repository(repo_analysis)
            
            if category not in categorization_results:
                categorization_results[category] = []
            categorization_results[category].append((repo, confidence))
            
            # Display result
            confidence_bar = "█" * int(confidence * 20)
            print(f"📍 {repo['name']:<20} → {category}")
            print(f"   Confidence: {confidence:.3f} {confidence_bar}")
            print(f"   Topics: {', '.join(repo['topics'][:4])}")
            print(f"   Language: {repo['language']} | ⭐ {repo['stars']:,}")
            print()
        
        print("📊 Categorization Summary:")
        print("-" * 30)
        for category, repos in sorted(categorization_results.items()):
            avg_confidence = sum(conf for _, conf in repos) / len(repos)
            print(f"   {category}: {len(repos)} repos (avg confidence: {avg_confidence:.3f})")
        
        print()
        print("✨ This demonstrates how the system automatically organizes")
        print("   starred repositories into meaningful categories!")
        print()
        print("🚀 To use with your starred repositories:")
        print("   1. Set GITHUB_TOKEN environment variable")
        print("   2. Run: python scripts/star_organizer.py")
        print("   3. Or use the GitHub Actions workflow for automation")
        
    except ImportError as e:
        print(f"❌ Error: {e}")
        print("Please install dependencies: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    demo_categorization()