#!/usr/bin/env node

// Simple test script for Credly badges functionality

const { fetchCredlyBadges, generateBadgesMarkdown } = require('./fetch-credly-badges');

async function testCredlyFetch() {
    console.log('🧪 Testing Credly badge fetching...\n');
    
    try {
        // Test with a known username
        const testUsername = 'sagar-gupta.f8eb96cc';
        console.log(`Testing with username: ${testUsername}`);
        
        const badges = await fetchCredlyBadges(testUsername);
        
        console.log(`\n✅ Successfully fetched ${badges.length} badges`);
        
        if (badges.length > 0) {
            console.log('\n📋 Sample badge data:');
            console.log(JSON.stringify(badges[0], null, 2));
            
            console.log('\n📝 Generated markdown preview:');
            const markdown = generateBadgesMarkdown(badges.slice(0, 2)); // Just show first 2
            console.log(markdown);
        } else {
            console.log('\n⚠️  No badges found. This could mean:');
            console.log('   - The username has no public badges');
            console.log('   - The Credly profile is private');
            console.log('   - There was an API issue');
        }
        
    } catch (error) {
        console.error('\n❌ Test failed:', error.message);
        process.exit(1);
    }
}

// Run test if this file is executed directly
if (require.main === module) {
    testCredlyFetch();
}
