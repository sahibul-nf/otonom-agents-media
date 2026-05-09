'use strict';

const sharp = require('sharp');
const path = require('path');
const fs = require('fs');

/**
 * Adds a professional watermark bar to the bottom of an image.
 * @param {string} inputPath Path to source image
 * @param {string} outputPath Path to save watermarked image
 * @param {string} text Brand text (default: TechTalk Intel)
 */
async function addWatermark(inputPath, outputPath, text = 'TechTalk Intel') {
  try {
    const image = sharp(inputPath);
    const metadata = await image.metadata();
    const width = metadata.width;
    const height = metadata.height;

    // Bar height (approx 8% of image height)
    const barHeight = Math.floor(height * 0.08);
    const fontSize = Math.floor(barHeight * 0.5);

    // Create a semi-transparent black bar
    const svgBar = `
      <svg width="${width}" height="${barHeight}">
        <rect x="0" y="0" width="${width}" height="${barHeight}" fill="rgba(0,0,0,0.6)" />
        <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="white" font-family="Arial, sans-serif" font-weight="bold" font-size="${fontSize}">
          ${text}
        </text>
      </svg>
    `;

    await image
      .composite([
        {
          input: Buffer.from(svgBar),
          top: height - barHeight,
          left: 0,
        },
      ])
      .toFile(outputPath);

    return outputPath;
  } catch (e) {
    console.error('❌ Watermark error:', e.message);
    return inputPath; // Fallback to original
  }
}

module.exports = { addWatermark };
