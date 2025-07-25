#!/usr/bin/env python3
"""
Credly Badges Fetcher - Python Version
Fetches public badges from Credly profile and generates markdown
"""

import json
import os
import urllib.request
import urllib.error
import re
from datetime import datetime
from typing import List, Dict, Any

# Configuration
CREDLY_USERNAME = os.environ.get('CREDLY_USERNAME', 'sagar-gupta.f8eb96cc')
OUTPUT_DIR = 'badges'
BADGES_JSON_FILE = os.path.join(OUTPUT_DIR, 'credly-badges.json')
BADGES_MD_FILE = os.path.join(OUTPUT_DIR, 'credly-badges.md')

def ensure_output_dir():
    """Ensure output directory exists"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_url(url: str, timeout: int = 10) -> str:
    """Fetch content from URL with error handling"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except urllib.error.URLError as e:
        raise Exception(f"Failed to fetch {url}: {e}")

def fetch_credly_badges(username: str) -> List[Dict[str, Any]]:
    """Fetch badges from Credly profile"""
    print(f"Fetching badges for username: {username}")
    
    try:
        # Try JSON API endpoint first
        json_url = f"https://www.credly.com/users/{username}/badges.json"
        print(f"Trying JSON API: {json_url}")
        
        try:
            content = fetch_url(json_url)
            data = json.loads(content)
            
            if 'data' in data and isinstance(data['data'], list):
                badges = []
                for badge in data['data']:
                    badge_info = {
                        'id': badge.get('id', f'badge-{len(badges) + 1}'),
                        'title': badge.get('badge_template', {}).get('name', 'Unknown Badge'),
                        'description': badge.get('badge_template', {}).get('description', ''),
                        'image_url': badge.get('badge_template', {}).get('image_url', badge.get('image_url', '')),
                        'public_url': badge.get('public_url', ''),
                        'issued_at': badge.get('issued_at', datetime.now().isoformat()),
                        'expires_at': badge.get('expires_at'),
                        'issuer': {
                            'name': badge.get('badge_template', {}).get('issuer', {}).get('name', 
                                           badge.get('issuer', {}).get('name', 'Credly')),
                            'url': badge.get('badge_template', {}).get('issuer', {}).get('url',
                                          badge.get('issuer', {}).get('url', 'https://credly.com'))
                        },
                        'skills': badge.get('badge_template', {}).get('skills', [])
                    }
                    badges.append(badge_info)
                
                print(f"Successfully fetched {len(badges)} badges via JSON API")
                return badges
        
        except Exception as e:
            print(f"JSON API failed: {e}")
            pass
        
        # Fallback: Try scraping the HTML page
        print("Trying HTML scraping fallback...")
        html_url = f"https://www.credly.com/users/{username}"
        html_content = fetch_url(html_url)
        
        # Extract badge information from HTML using regex
        badges = []
        
        # Look for badge containers in the HTML
        badge_pattern = r'<div[^>]*class="[^"]*badge[^"]*"[^>]*>.*?</div>'
        image_pattern = r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*>'
        link_pattern = r'<a[^>]*href="([^"]*)"[^>]*>'
        
        # Find all potential badge sections
        import re
        badge_matches = re.findall(badge_pattern, html_content, re.DOTALL | re.IGNORECASE)
        
        for i, badge_html in enumerate(badge_matches[:10]):  # Limit to first 10 matches
            # Extract image and title
            img_match = re.search(image_pattern, badge_html, re.IGNORECASE)
            link_match = re.search(link_pattern, badge_html, re.IGNORECASE)
            
            if img_match:
                image_url = img_match.group(1)
                title = img_match.group(2) if len(img_match.groups()) > 1 else f"Badge {i+1}"
                
                # Clean up image URL if it's relative
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                elif image_url.startswith('/'):
                    image_url = 'https://www.credly.com' + image_url
                
                # Clean up link URL
                public_url = link_match.group(1) if link_match else ''
                if public_url.startswith('//'):
                    public_url = 'https:' + public_url
                elif public_url.startswith('/'):
                    public_url = 'https://www.credly.com' + public_url
                
                badge_info = {
                    'id': f'badge-{i+1}',
                    'title': title.strip(),
                    'description': '',
                    'image_url': image_url,
                    'public_url': public_url,
                    'issued_at': datetime.now().isoformat(),
                    'expires_at': None,
                    'issuer': {
                        'name': 'Credly',
                        'url': 'https://credly.com'
                    },
                    'skills': []
                }
                badges.append(badge_info)
        
        print(f"HTML scraping found {len(badges)} potential badges")
        return badges
        
    except Exception as e:
        print(f"Error fetching badges: {e}")
        return []

def generate_badges_markdown(badges: List[Dict[str, Any]]) -> str:
    """Generate markdown for badges"""
    if not badges:
        return '<!-- No Credly badges found -->\n'
    
    markdown = '## 🏆 Credly Certificates & Badges\n\n'
    markdown += '<div align="center">\n\n'
    
    # Sort badges by issued date (newest first)
    try:
        badges_sorted = sorted(badges, key=lambda x: x.get('issued_at', ''), reverse=True)
    except:
        badges_sorted = badges
    
    # Create grid layout for badges
    badges_per_row = 4
    for i in range(0, len(badges_sorted), badges_per_row):
        row_badges = badges_sorted[i:i + badges_per_row]
        
        for badge in row_badges:
            image_url = badge['image_url']
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            
            badge_url = badge['public_url']
            if badge_url.startswith('//'):
                badge_url = 'https:' + badge_url
            
            markdown += f'<a href="{badge_url}" target="_blank" rel="noreferrer">\n'
            markdown += f'  <img src="{image_url}" alt="{badge["title"]}" width="120" height="120" style="margin: 10px;" />\n'
            markdown += f'</a>\n'
        
        markdown += '\n'
    
    markdown += '</div>\n\n'
    
    # Add detailed table
    markdown += '<details>\n<summary><h3>📋 Badge Details</h3></summary>\n\n'
    markdown += '| Badge | Issuer | Issued Date | Skills |\n'
    markdown += '|-------|--------|-------------|--------|\n'
    
    for badge in badges_sorted:
        try:
            issued_date = datetime.fromisoformat(badge['issued_at'].replace('Z', '+00:00')).strftime('%b %d, %Y')
        except:
            issued_date = 'Unknown'
        
        skills = []
        if badge.get('skills'):
            for skill in badge['skills'][:3]:  # Show max 3 skills
                if isinstance(skill, dict):
                    skills.append(skill.get('name', str(skill)))
                else:
                    skills.append(str(skill))
        
        skills_str = ', '.join(skills) if skills else '-'
        
        image_url = badge['image_url']
        if image_url.startswith('//'):
            image_url = 'https:' + image_url
        
        badge_url = badge['public_url']
        if badge_url.startswith('//'):
            badge_url = 'https:' + badge_url
        
        markdown += f'| [<img src="{image_url}" width="40" height="40" />]({badge_url}) [{badge["title"]}]({badge_url}) | {badge["issuer"]["name"]} | {issued_date} | {skills_str} |\n'
    
    markdown += '\n</details>\n\n'
    
    return markdown

def main():
    """Main function"""
    try:
        print('Starting Credly badges fetch...')
        
        ensure_output_dir()
        
        badges = fetch_credly_badges(CREDLY_USERNAME)
        
        # Save badges data as JSON
        with open(BADGES_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(badges, f, indent=2, ensure_ascii=False)
        print(f'Saved {len(badges)} badges to {BADGES_JSON_FILE}')
        
        # Generate markdown
        markdown = generate_badges_markdown(badges)
        with open(BADGES_MD_FILE, 'w', encoding='utf-8') as f:
            f.write(markdown)
        print(f'Generated markdown file: {BADGES_MD_FILE}')
        
        # Output summary
        print('\n--- Summary ---')
        print(f'Total badges found: {len(badges)}')
        print(f'JSON file: {BADGES_JSON_FILE}')
        print(f'Markdown file: {BADGES_MD_FILE}')
        
        if badges:
            print('\nRecent badges:')
            for badge in badges[:3]:
                print(f'- {badge["title"]} ({badge["issuer"]["name"]})')
        
    except Exception as e:
        print(f'Error in main function: {e}')
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
