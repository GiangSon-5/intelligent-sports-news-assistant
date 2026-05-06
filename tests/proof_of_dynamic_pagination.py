import asyncio
from playwright.async_api import async_playwright

class DynamicPaginationPOC:
    """
    Proof of Concept (PoC) for discovering hidden Ajax pagination endpoints
    using browser automation and network traffic analysis.
    """

    def __init__(self, target_url):
        self.target_url = target_url
        self.ajax_endpoints = set()
        self.static_links = set()

    async def capture_network_requests(self, request):
        """
        Callback function to intercept network requests and filter 
        strictly for pagination/timeline endpoints.
        """
        url = request.url
        
        # 1. Skip static assets & ads (Noise reduction)
        noise_extensions = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".css", ".js", ".woff", ".webp")
        noise_domains = ("doubleclick", "adn", "admicro", "rubiconproject", "vnecdn", "google", "facebook", "sync", "logging")
        
        if url.lower().endswith(noise_extensions) or any(d in url.lower() for d in noise_domains):
            return

        # 2. Match only the "Gold" endpoints (Ajax)
        if "timelinelist" in url or "timeline" in url:
            if "thanhnien.vn" in url or "tuoitre.vn" in url:
                if ".htm" in url or "/trang-" in url:
                    self.ajax_endpoints.add(url)

    async def execute_discovery(self):
        """
        Main execution flow: initializes browser, triggers scrolls, 
        and captures dynamic requests + static pagination links.
        """
        print("-" * 80)
        print(f"Executing Multi-Mode Discovery for: {self.target_url}")
        print("-" * 80)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Register network request listener
            page.on("request", self.capture_network_requests)

            try:
                # Navigate to target page
                await page.goto(self.target_url, wait_until="domcontentloaded", timeout=60000)
                
                # 1. Discovery Mode: STATIC (Scanning DOM)
                print("Scanning for Static Pagination links (DOM)...")
                # Looking for patterns like btn-page, next-page, p2, p3...
                selectors = [
                    "a.btn-page", "a.next-page", "a[href*='-p2']", 
                    "a[href*='trang-2']", "a[rel='next']", ".paging a"
                ]
                for selector in selectors:
                    elements = await page.locator(selector).element_handles()
                    for el in elements:
                        href = await el.get_attribute("href")
                        if href and not href.startswith("javascript"):
                            full_url = await page.evaluate(f"(h) => new URL(h, '{self.target_url}').href", href)
                            self.static_links.add(full_url)

                # 2. Discovery Mode: DYNAMIC (Scrolling)
                print("Scrolling viewport to trigger Dynamic Ajax loading...")
                for i in range(15):
                    await page.evaluate("window.scrollBy(0, 1500)")
                    await asyncio.sleep(1.0)
                    
                    # Try to click navigation buttons to trigger network events
                    try:
                        btn = page.locator("a:has-text('Xem thêm'), button:has-text('Xem thêm'), a.next-page")
                        if await btn.is_visible():
                            await btn.click()
                            await asyncio.sleep(1.0)
                    except:
                        pass

                # --- Summary Report for HR/Stakeholders ---
                print(f"\n[FINAL DISCOVERY REPORT - {self.target_url}]")
                
                # Report Dynamic Results
                if self.ajax_endpoints:
                    print(f"📡 DYNAMIC MODE: SUCCESS - Captured {len(self.ajax_endpoints)} Ajax endpoint(s)")
                    for endpoint in sorted(self.ajax_endpoints)[:10]: # Show top 10
                        print(f"   -> [API] {endpoint}")
                else:
                    print("📡 DYNAMIC MODE: Not detected (No Ajax/Infinite scroll).")

                # Report Static Results
                if self.static_links:
                    print(f"📄 STATIC MODE: SUCCESS - Found {len(self.static_links)} navigation link(s)")
                    for link in sorted(self.static_links)[:10]: # Show top 10
                        print(f"   -> [PAGE] {link}")
                else:
                    print("📄 STATIC MODE: No standard pagination links found in DOM.")

                print("\n[CONCLUSION]")
                if self.ajax_endpoints:
                    print("=> Website uses AJAX. Recommendation: Use direct API calls.")
                elif self.static_links:
                    print("=> Website uses STATIC PAGING. Recommendation: Use URL pattern generation.")
                else:
                    print("=> Complex site structure. Manual analysis required.")

            except Exception as e:
                print(f"ERROR: Execution failed: {e}")
            
            finally:
                await browser.close()
                print("-" * 80)
                print(f"Discovery Complete for {self.target_url}")
                print("-" * 80)

async def main():
    targets = [
        "https://thanhnien.vn/the-thao.htm",
        "https://tuoitre.vn/the-thao.htm",
        "https://vnexpress.net/the-thao"
    ]
    
    for url in targets:
        poc = DynamicPaginationPOC(url)
        await poc.execute_discovery()

if __name__ == "__main__":
    asyncio.run(main())
