DigiScience Tech Solutions - cPanel Ready SEO update
===================================================

What was updated
----------------
1. sitemap.xml was cleaned up and now contains the real public page URL only.
2. robots.txt now points to the live sitemap URL at https://digisciencetechsol.com/sitemap.xml
3. Meta tags were improved on every HTML page:
   - Title
   - Description
   - Canonical URL
   - Open Graph tags
   - Twitter card tags
4. A social share image was added at assets/social-share.svg for LinkedIn, WhatsApp, Facebook, and other previews.
5. The success page was marked noindex so it does not get indexed by search engines.
6. Performance-oriented improvements were applied:
   - removed external Google Font dependency to reduce render-blocking requests
   - preloaded style.css
   - deferred JavaScript loading
   - added image width/height and async decoding on the logo
   - added reduced-motion support and stronger focus states
7. Google Analytics event tracking for successful enquiry submission was added.

Search Console steps
--------------------
1. Upload this package to your hosting root.
2. Open Google Search Console.
3. Add or verify the property for https://digisciencetechsol.com
4. Submit this sitemap URL:
   https://digisciencetechsol.com/sitemap.xml

PageSpeed note
--------------
The code has been updated for better Core Web Vitals and PageSpeed results.
To run the actual test, use the live URL in https://pagespeed.web.dev after deployment.
Target guideline: 90+ on mobile and desktop, but the real score will still depend on hosting, caching, server response time, and Google Analytics load timing.

Public pages in this package
----------------------------
- https://digisciencetechsol.com/

Non-indexed utility page
------------------------
- https://digisciencetechsol.com/success.html
  This page exists for form confirmation only and is intentionally excluded from sitemap indexing.
