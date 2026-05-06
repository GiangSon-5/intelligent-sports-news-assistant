import asyncio
from playwright.async_api import async_playwright

# Configure news sources and corresponding selectors from SPEC §3.2
SOURCES = [
    {
        "name": "THANH NIÊN",
        "url": "https://thanhnien.vn/the-thao.htm",
        "parent": ".box-category-item",
        "title": "h3.box-title-text a, h2.box-title-text a"
    },
    {
        "name": "VNEXPRESS",
        "url": "https://vnexpress.net/the-thao",
        "parent": "article.item-news",
        "title": "h2.title-news a, h3.title-news a"
    },
    {
        "name": "TUỔI TRẺ",
        "url": "https://tuoitre.vn/the-thao.htm",
        "parent": ".box-category-item, .box-content",
        "title": "h3.box-title-text a, h2.box-title-text a, .box-category-title a"
    }
]

async def highlight_page(page, source):
    """Open a news page and perform continuous data highlighting."""
    try:
        print(f"Connecting to: {source['name']}...")
        await page.goto(source['url'], wait_until="domcontentloaded", timeout=60000)
        
        # Inject script to monitor and highlight new elements (Supports Lazy Loading)
        await page.evaluate(f'''(sourceInfo) => {{
            setInterval(() => {{
                // Find unprocessed parent blocks
                const parents = document.querySelectorAll(sourceInfo.parent + ':not(.marked-by-bot)');
                
                parents.forEach(p => {{
                    p.classList.add('marked-by-bot');
                    p.style.border = '3px solid red';
                    p.style.position = 'relative';
                    p.style.transition = 'all 0.3s';
                    
                    // Add identification label for Parent Block
                    const label = document.createElement('span');
                    label.innerText = sourceInfo.name + ' - CHUẨN';
                    label.style.cssText = 'background:red; color:white; font-size:9px; font-weight:bold; padding:1px 4px; position:absolute; top:0; left:0; z-index:1000; font-family:sans-serif;';
                    p.appendChild(label);

                    // Find and highlight internal Title/Link
                    const title = p.querySelector(sourceInfo.title);
                    if (title) {{
                        title.style.backgroundColor = 'rgba(255, 255, 0, 0.6)';
                        title.style.border = '1px dashed green';
                    }}
                }});
            }}, 500);
        }}''', source)
        print(f"Highlighting filter activated for: {source['name']}")
    except Exception as e:
        print(f"Error opening {source['name']}: {e}")

async def visual_test_multi_tabs():
    """Main function controlling 3 browser tabs concurrently."""
    async with async_playwright() as p:
        # Launch browser (non-headless)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        # Initialize tab opening tasks
        tasks = []
        for source in SOURCES:
            page = await context.new_page()
            tasks.append(highlight_page(page, source))
        
        # Execute parallel tab processing
        await asyncio.gather(*tasks)
        
        print("\n" + "═"*60)
        print("ALL SYSTEMS READY!")
        print("1. Thanh Niên - Tab 1")
        print("2. VnExpress  - Tab 2")
        print("3. Tuổi Trẻ   - Tab 3")
        print("\nPlease switch between tabs and scroll to verify highlighting accuracy.")
        print("Press ENTER here to terminate the demo session.")
        print("═"*60)
        
        # Wait for user review
        await asyncio.get_event_loop().run_in_executor(None, input)
        await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(visual_test_multi_tabs())
    except KeyboardInterrupt:
        pass
