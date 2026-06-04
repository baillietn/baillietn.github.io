import puppeteer from 'puppeteer';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

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
      deviceScaleFactor: 1
    });

    const cvPath = `file://${path.resolve(__dirname, 'cv/index.html')}`;
    console.log('Loading: cv/index.html');
    await page.goto(cvPath, { waitUntil: 'networkidle2' });

    await page.evaluate(() => {
      document.documentElement.removeAttribute('data-theme');
      
      document.querySelector('.btn-container').style.display = 'none';
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

    await page.waitForTimeout(300);

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

    await browser.close();

    const fileSizeKb = (fs.statSync(pdfPath).size / 1024).toFixed(2);
    console.log('Success!');
    console.log(`File size: ${fileSizeKb} KB`);
    console.log('Saved: cv/cv-nicolas-bailliet.pdf');

  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  } finally {
    if (browser) await browser.close();
  }
})();
