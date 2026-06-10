import puppeteer from 'puppeteer';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  let browser;
  try {
    console.log('Launching Chromium...');
    browser = await puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();

    const A4_WIDTH = 794;
    const A4_HEIGHT = 1123;

    await page.setViewport({
      width: A4_WIDTH,
      height: A4_HEIGHT,
      deviceScaleFactor: 2 
    });

    const cvPath = `file://${path.resolve(__dirname, 'cv/index.html')}`;
    console.log('Loading: cv/index.html');
    await page.goto(cvPath, { waitUntil: 'networkidle2' });

    await page.evaluate(() => {
      document.documentElement.removeAttribute('data-theme');

      const hide = (sel) => { const el = document.querySelector(sel); if (el) el.style.display = 'none'; };
      hide('.btn-container');
      hide('.btn-container-right');

      document.documentElement.style.overflow = 'hidden';
      document.body.style.padding = '0';
      document.body.style.background = 'white';
      document.body.style.margin = '0';
      document.body.style.overflow = 'hidden';

      const container = document.querySelector('.cv-container');
      container.style.boxShadow = 'none';
      container.style.margin = '0';
      container.style.maxWidth = '210mm';
      container.style.height = '297mm';
      container.style.overflow = 'hidden';
    });

    await sleep(300);

    const pdfPath = path.resolve(__dirname, 'cv/cv-nicolas-bailliet.pdf');
    console.log('Generating PDF...');
    await page.pdf({
      path: pdfPath,
      format: 'A4',
      margin: 0,
      displayHeaderFooter: false,
      printBackground: true,
      preferCSSPageSize: true,
      scale: 1,
      timeout: 30000
    });
    const pdfKb = (fs.statSync(pdfPath).size / 1024).toFixed(2);
    console.log(`  -> cv/cv-nicolas-bailliet.pdf (${pdfKb} KB)`);

    const thumbPath = path.resolve(__dirname, 'cv/_cv-thumb.png');
    const cvEl = await page.$('.cv-container');
    await cvEl.screenshot({ path: thumbPath });
    console.log('  -> CV thumbnail captured');

    const composer = `<!doctype html><html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;600&family=IBM+Plex+Sans:wght@300;400;600&family=IBM+Plex+Serif:wght@600&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:1200px;height:630px;overflow:hidden}
  .og{width:1200px;height:630px;position:relative;display:flex;align-items:center;overflow:hidden;
    color:#eaf3ff;font-family:'IBM Plex Sans',system-ui,sans-serif;
    background:
      radial-gradient(720px 520px at 16% 18%, rgba(0,180,216,.22), transparent 60%),
      radial-gradient(760px 620px at 96% 92%, rgba(15,95,143,.28), transparent 60%),
      linear-gradient(135deg,#0a1626 0%,#0f2740 58%,#091826 100%);}
  .txt{padding-left:84px;width:640px;z-index:2}
  .eyebrow{font-family:'IBM Plex Mono',monospace;font-size:15px;letter-spacing:.3em;
    text-transform:uppercase;color:#5fd0f0;margin-bottom:16px}
  .name{font-family:'IBM Plex Serif',Georgia,serif;font-weight:600;font-size:64px;line-height:1.0;letter-spacing:-.01em}
  .role{font-size:23px;color:#c3e7f5;font-weight:300;margin-top:16px;max-width:520px;line-height:1.35}
  .chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:28px}
  .chip{font-family:'IBM Plex Mono',monospace;font-size:13px;color:#d6efff;
    border:1px solid rgba(120,200,235,.30);background:rgba(10,30,52,.5);border-radius:999px;padding:6px 12px}
  .cta{font-family:'IBM Plex Mono',monospace;font-size:15px;color:#7fe0ff;margin-top:30px;letter-spacing:.02em}
  .thumbwrap{position:absolute;right:88px;top:50%;transform:translateY(-50%) rotate(-2.5deg);
    filter:drop-shadow(0 28px 48px rgba(0,0,0,.55))}
  .thumb{height:548px;width:auto;display:block;border-radius:10px;border:1px solid rgba(255,255,255,.18)}
</style></head>
<body>
  <div class="og">
    <div class="txt">
      <div class="eyebrow">Curriculum Vitae</div>
      <div class="name">Nicolas<br>Bailliet</div>
      <div class="role">LLM / Deep Learning — model training, architecture &amp; inference</div>
      <div class="chips">
        <span class="chip">HilbertLM</span>
        <span class="chip">ENSEEIHT</span>
        <span class="chip">PyTorch · Python</span>
      </div>
      <div class="cta">↗ baillietn.github.io/cv</div>
    </div>
    <div class="thumbwrap"><img class="thumb" src="_cv-thumb.png" alt="CV"></div>
  </div>
</body></html>`;

    const ogTempPath = path.resolve(__dirname, 'cv/_og-temp.html');
    fs.writeFileSync(ogTempPath, composer, 'utf-8');

    const ogPage = await browser.newPage();
    await ogPage.setViewport({ width: 1200, height: 630, deviceScaleFactor: 2 });
    await ogPage.goto(`file://${ogTempPath}`, { waitUntil: 'networkidle0' });
    try { await ogPage.evaluate(() => document.fonts.ready); } catch (e) {}
    await sleep(250);

    const ogPath = path.resolve(__dirname, 'cv/og-cv.png');
    await ogPage.screenshot({ path: ogPath }); 
    const ogKb = (fs.statSync(ogPath).size / 1024).toFixed(2);
    console.log(`  -> cv/og-cv.png (${ogKb} KB)`);

    // cleanup temp files
    fs.unlinkSync(thumbPath);
    fs.unlinkSync(ogTempPath);

    await browser.close();

    console.log('');
    console.log('Success! Generated:');
    console.log('  - cv/cv-nicolas-bailliet.pdf  (downloadable CV)');
    console.log('  - cv/og-cv.png                (LinkedIn / social thumbnail, 1200x630)');

  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  } finally {
    if (browser) await browser.close();
  }
})();
