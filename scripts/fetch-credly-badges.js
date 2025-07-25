const https = require('https');
const fs = require('fs');
const path = require('path');

// Configuration
const CREDLY_USERNAME = process.env.CREDLY_USERNAME || 'sagar-gupta.f8eb96cc';
const OUTPUT_DIR = 'badges';
const BADGES_JSON_FILE = path.join(OUTPUT_DIR, 'credly-badges.json');
const BADGES_MD_FILE = path.join(OUTPUT_DIR, 'credly-badges.md');

// Ensure output directory exists
if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

// Function to make HTTPS requests
function httpsRequest(url) {
    return new Promise((resolve, reject) => {
        const req = https.get(url, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                if (res.statusCode === 200) {
                    resolve(data);
                } else {
                    reject(new Error(`HTTP ${res.statusCode}: ${res.statusMessage}`));
                }
            });
        });
        
        req.on('error', (err) => {
            reject(err);
        });
        
        req.setTimeout(10000, () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });
    });
}

// Function to fetch user's public badges from Credly
async function fetchCredlyBadges(username) {
    try {
        console.log(`Fetching badges for username: ${username}`);
        
        // Credly public API endpoint for user badges
        const url = `https://www.credly.com/users/${username}/badges.json`;
        
        const response = await httpsRequest(url);
        const data = JSON.parse(response);
        
        if (!data.data || !Array.isArray(data.data)) {
            throw new Error('Invalid response format from Credly API');
        }
        
        const badges = data.data.map(badge => ({
            id: badge.id,
            title: badge.badge_template?.name || 'Unknown Badge',
            description: badge.badge_template?.description || '',
            image_url: badge.badge_template?.image_url || badge.image_url,
            public_url: badge.public_url,
            issued_at: badge.issued_at,
            expires_at: badge.expires_at,
            issuer: {
                name: badge.badge_template?.issuer?.name || badge.issuer?.name,
                url: badge.badge_template?.issuer?.url || badge.issuer?.url
            },
            skills: badge.badge_template?.skills || []
        }));
        
        console.log(`Successfully fetched ${badges.length} badges`);
        return badges;
        
    } catch (error) {
        console.error('Error fetching Credly badges:', error.message);
        
        // Try alternative approach - scraping public profile
        return await fetchCredlyBadgesAlternative(username);
    }
}

// Alternative method to fetch badges (fallback)
async function fetchCredlyBadgesAlternative(username) {
    try {
        console.log('Trying alternative method to fetch badges...');
        
        const url = `https://www.credly.com/users/${username}`;
        const html = await httpsRequest(url);
        
        // Simple regex to extract badge information from HTML
        const badgeRegex = /<div[^>]*class="[^"]*badge[^"]*"[^>]*>[\s\S]*?<\/div>/gi;
        const titleRegex = /<h3[^>]*>(.*?)<\/h3>/i;
        const imageRegex = /<img[^>]*src="([^"]*)"[^>]*>/i;
        const linkRegex = /<a[^>]*href="([^"]*)"[^>]*>/i;
        
        const badges = [];
        let match;
        
        while ((match = badgeRegex.exec(html)) !== null) {
            const badgeHtml = match[0];
            const titleMatch = titleRegex.exec(badgeHtml);
            const imageMatch = imageRegex.exec(badgeHtml);
            const linkMatch = linkRegex.exec(badgeHtml);
            
            if (titleMatch && imageMatch) {
                badges.push({
                    id: `badge-${badges.length + 1}`,
                    title: titleMatch[1].trim(),
                    description: '',
                    image_url: imageMatch[1],
                    public_url: linkMatch ? linkMatch[1] : '',
                    issued_at: new Date().toISOString(),
                    expires_at: null,
                    issuer: {
                        name: 'Credly',
                        url: 'https://credly.com'
                    },
                    skills: []
                });
            }
        }
        
        console.log(`Alternative method found ${badges.length} badges`);
        return badges;
        
    } catch (error) {
        console.error('Alternative method also failed:', error.message);
        return [];
    }
}

// Function to generate markdown for badges
function generateBadgesMarkdown(badges) {
    if (badges.length === 0) {
        return '<!-- No Credly badges found -->\n';
    }
    
    let markdown = '## 🏆 Credly Certificates & Badges\n\n';
    markdown += '<div align="center">\n\n';
    
    // Sort badges by issued date (newest first)
    const sortedBadges = badges.sort((a, b) => new Date(b.issued_at) - new Date(a.issued_at));
    
    // Create a grid layout for badges
    const badgesPerRow = 4;
    for (let i = 0; i < sortedBadges.length; i += badgesPerRow) {
        const rowBadges = sortedBadges.slice(i, i + badgesPerRow);
        
        rowBadges.forEach(badge => {
            const imageUrl = badge.image_url.startsWith('//') ? `https:${badge.image_url}` : badge.image_url;
            const badgeUrl = badge.public_url.startsWith('//') ? `https:${badge.public_url}` : badge.public_url;
            
            markdown += `<a href="${badgeUrl}" target="_blank" rel="noreferrer">\n`;
            markdown += `  <img src="${imageUrl}" alt="${badge.title}" width="120" height="120" style="margin: 10px;" />\n`;
            markdown += `</a>\n`;
        });
        
        markdown += '\n';
    }
    
    markdown += '</div>\n\n';
    
    // Add a table with badge details
    markdown += '<details>\n<summary><h3>📋 Badge Details</h3></summary>\n\n';
    markdown += '| Badge | Issuer | Issued Date | Skills |\n';
    markdown += '|-------|--------|-------------|--------|\n';
    
    sortedBadges.forEach(badge => {
        const issuedDate = new Date(badge.issued_at).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
        
        const skills = badge.skills.length > 0 
            ? badge.skills.slice(0, 3).map(skill => skill.name || skill).join(', ')
            : '-';
        
        const imageUrl = badge.image_url.startsWith('//') ? `https:${badge.image_url}` : badge.image_url;
        const badgeUrl = badge.public_url.startsWith('//') ? `https:${badge.public_url}` : badge.public_url;
        
        markdown += `| [<img src="${imageUrl}" width="40" height="40" />](${badgeUrl}) [${badge.title}](${badgeUrl}) | ${badge.issuer.name} | ${issuedDate} | ${skills} |\n`;
    });
    
    markdown += '\n</details>\n\n';
    
    return markdown;
}

// Main function
async function main() {
    try {
        console.log('Starting Credly badges fetch...');
        
        const badges = await fetchCredlyBadges(CREDLY_USERNAME);
        
        // Save badges data as JSON
        fs.writeFileSync(BADGES_JSON_FILE, JSON.stringify(badges, null, 2));
        console.log(`Saved ${badges.length} badges to ${BADGES_JSON_FILE}`);
        
        // Generate markdown
        const markdown = generateBadgesMarkdown(badges);
        fs.writeFileSync(BADGES_MD_FILE, markdown);
        console.log(`Generated markdown file: ${BADGES_MD_FILE}`);
        
        // Output summary
        console.log('\n--- Summary ---');
        console.log(`Total badges found: ${badges.length}`);
        console.log(`JSON file: ${BADGES_JSON_FILE}`);
        console.log(`Markdown file: ${BADGES_MD_FILE}`);
        
        if (badges.length > 0) {
            console.log('\nRecent badges:');
            badges.slice(0, 3).forEach(badge => {
                console.log(`- ${badge.title} (${badge.issuer.name})`);
            });
        }
        
    } catch (error) {
        console.error('Error in main function:', error);
        process.exit(1);
    }
}

// Run the script
if (require.main === module) {
    main();
}

module.exports = {
    fetchCredlyBadges,
    generateBadgesMarkdown
};
