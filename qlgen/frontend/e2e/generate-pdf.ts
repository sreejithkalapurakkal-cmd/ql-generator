/**
 * Generate a PDF of the qlGen User Guide with embedded screenshots.
 *
 * Usage:
 *   npx playwright test e2e/generate-pdf.ts
 *
 * Output:
 *   qlGen-User-Guide.pdf in the project root (qlgen/)
 */
import { test } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { marked } from 'marked';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const GUIDE_MD = path.join(PROJECT_ROOT, 'qlGen-User-Guide.md');
const SCREENSHOT_DIR = path.join(__dirname, '..', 'screenshots');
const OUTPUT_PDF = path.join(PROJECT_ROOT, 'qlGen-User-Guide.pdf');

/**
 * Read the markdown, convert images to base64 data URIs so they
 * render inline when Playwright prints to PDF.
 */
function buildHtml(): string {
  let md = fs.readFileSync(GUIDE_MD, 'utf-8');

  // Replace image references with base64 data URIs
  md = md.replace(
    /!\[([^\]]*)\]\(([^)]+)\)/g,
    (_match: string, alt: string, imgPath: string) => {
      // Resolve the image path relative to the markdown file location
      let absPath: string;
      if (path.isAbsolute(imgPath)) {
        absPath = imgPath;
      } else {
        absPath = path.resolve(PROJECT_ROOT, imgPath);
      }

      if (fs.existsSync(absPath)) {
        const buf = fs.readFileSync(absPath);
        const ext = path.extname(absPath).slice(1) || 'png';
        const b64 = buf.toString('base64');
        return `![${alt}](data:image/${ext};base64,${b64})`;
      }
      // If image not found, keep original reference
      return `![${alt}](${imgPath})`;
    },
  );

  const htmlBody = marked.parse(md) as string;

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<style>
  @page {
    size: A4;
    margin: 20mm 18mm 20mm 18mm;
  }

  * { box-sizing: border-box; }

  body {
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.55;
    color: #1a1a2e;
    max-width: 100%;
    padding: 0;
    margin: 0;
  }

  /* Headings */
  h1 {
    font-size: 26pt;
    color: #5C2D8F;
    border-bottom: 3px solid #5C2D8F;
    padding-bottom: 8px;
    margin-top: 0;
    margin-bottom: 12px;
    page-break-after: avoid;
  }

  h2 {
    font-size: 17pt;
    color: #5C2D8F;
    border-bottom: 1.5px solid #e0d4f0;
    padding-bottom: 4px;
    margin-top: 28px;
    margin-bottom: 10px;
    page-break-after: avoid;
  }

  h3 {
    font-size: 13pt;
    color: #333;
    margin-top: 20px;
    margin-bottom: 8px;
    page-break-after: avoid;
  }

  h4 {
    font-size: 11.5pt;
    color: #444;
    margin-top: 14px;
    margin-bottom: 6px;
    page-break-after: avoid;
  }

  /* Paragraphs */
  p {
    margin: 6px 0 10px 0;
    orphans: 3;
    widows: 3;
  }

  /* Links */
  a { color: #5C2D8F; text-decoration: none; }

  /* Lists */
  ul, ol {
    margin: 6px 0 10px 0;
    padding-left: 24px;
  }
  li { margin-bottom: 4px; }

  /* Tables */
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0 14px 0;
    font-size: 10pt;
    page-break-inside: avoid;
  }
  th {
    background: #f5f0fa;
    color: #5C2D8F;
    font-weight: 600;
    text-align: left;
    padding: 8px 10px;
    border: 1px solid #e0d4f0;
  }
  td {
    padding: 6px 10px;
    border: 1px solid #e8e8e8;
    vertical-align: top;
  }
  tr:nth-child(even) td { background: #fafafa; }

  /* Code */
  code {
    background: #f4f0fa;
    color: #5C2D8F;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 10pt;
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  }
  pre {
    background: #f8f6fc;
    border: 1px solid #e0d4f0;
    border-radius: 6px;
    padding: 12px 14px;
    overflow-x: auto;
    font-size: 9.5pt;
    line-height: 1.45;
    page-break-inside: avoid;
  }
  pre code {
    background: none;
    padding: 0;
    font-size: inherit;
  }

  /* Blockquotes (tips) */
  blockquote {
    margin: 10px 0 14px 0;
    padding: 10px 14px 10px 16px;
    border-left: 4px solid #5C2D8F;
    background: #f9f6fd;
    color: #333;
    border-radius: 0 6px 6px 0;
    page-break-inside: avoid;
  }
  blockquote p { margin: 4px 0; }

  /* Horizontal rules */
  hr {
    border: none;
    border-top: 1.5px solid #e0d4f0;
    margin: 24px 0;
  }

  /* Images (screenshots) */
  img {
    max-width: 100%;
    height: auto;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    margin: 10px 0 14px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    page-break-inside: avoid;
    display: block;
  }

  /* Strong / Bold */
  strong { color: #1a1a2e; }

  /* Emphasis */
  em { color: #555; }

  /* Page break hints */
  h2 { page-break-before: auto; }
  img + h2, img + h3 { page-break-before: always; }

  /* Table of Contents */
  #table-of-contents {
    page-break-after: always;
  }
  #table-of-contents + hr {
    display: none;
  }
  #table-of-contents ~ ol,
  #table-of-contents + ol {
    page-break-after: always;
  }
  /* Style the ToC list that follows the ToC heading */
  h2#table-of-contents {
    font-size: 20pt;
    margin-top: 16px;
    margin-bottom: 16px;
  }
  h2#table-of-contents + ol {
    font-size: 12pt;
    line-height: 1.9;
    padding-left: 22px;
    page-break-after: always;
  }
  h2#table-of-contents + ol > li {
    margin-bottom: 2px;
  }
  h2#table-of-contents + ol ul,
  h2#table-of-contents + ol ol {
    font-size: 11pt;
    line-height: 1.7;
    margin-top: 2px;
    margin-bottom: 4px;
    list-style-type: disc;
    padding-left: 22px;
  }
  h2#table-of-contents + ol a {
    color: #5C2D8F;
    text-decoration: none;
  }
  h2#table-of-contents + ol a:hover {
    text-decoration: underline;
  }

  /* Cover styling for first heading */
  body > h1:first-child {
    font-size: 32pt;
    text-align: center;
    border-bottom: none;
    margin-top: 40px;
    margin-bottom: 4px;
  }
  body > h1:first-child + p {
    text-align: center;
    font-size: 13pt;
    color: #666;
    margin-bottom: 30px;
  }
  body > h1:first-child + p + hr {
    margin-bottom: 30px;
  }
</style>
</head>
<body>
${htmlBody}
</body>
</html>`;
}

test('Generate User Guide PDF', async ({ page }) => {
  test.setTimeout(120_000);

  const html = buildHtml();

  // Write temp HTML file so Playwright can load it
  const tmpHtml = path.join(__dirname, '..', '_guide_tmp.html');
  fs.writeFileSync(tmpHtml, html, 'utf-8');

  try {
    await page.goto(`file://${tmpHtml}`, { waitUntil: 'networkidle' });

    // Let images render
    await page.waitForTimeout(2000);

    await page.pdf({
      path: OUTPUT_PDF,
      format: 'A4',
      printBackground: true,
      margin: {
        top: '20mm',
        bottom: '20mm',
        left: '18mm',
        right: '18mm',
      },
      displayHeaderFooter: true,
      headerTemplate: `
        <div style="width:100%; font-size:8pt; color:#999; padding:0 18mm; display:flex; justify-content:space-between;">
          <span>qlGen User Guide</span>
          <span></span>
        </div>`,
      footerTemplate: `
        <div style="width:100%; font-size:8pt; color:#999; padding:0 18mm; display:flex; justify-content:space-between;">
          <span>Confidential</span>
          <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
        </div>`,
    });

    console.log(`\nPDF generated: ${OUTPUT_PDF}`);
    const stat = fs.statSync(OUTPUT_PDF);
    console.log(`Size: ${(stat.size / 1024 / 1024).toFixed(1)} MB`);
  } finally {
    // Clean up temp file
    if (fs.existsSync(tmpHtml)) fs.unlinkSync(tmpHtml);
  }
});
