const fs = require('fs');
const path = require('path');
const { PNG } = require('pngjs');
const jpeg = require('jpeg-js');
const { GIFEncoder, quantize, applyPalette } = require('gifenc');

const base = '/home/ubuntu/.openclaw/workspace-projecta/JobRadar';
const files = [
  path.join('/home/ubuntu/.openclaw/media/browser','0dcbbb93-5669-4af0-a449-9279fc12247d.jpg'),
  path.join('/home/ubuntu/.openclaw/media/browser','ba2a630c-cf0a-4d07-8351-4bce2b287ffc.png'),
  path.join('/home/ubuntu/.openclaw/media/browser','09e584bc-dcd6-42f2-9ea0-59fd6bd2c589.png'),
];
const labels = ['1. Discover jobs','2. Enrich with job intelligence','3. Expand by company'];
const outPath = path.join(base, 'docs/demo.gif');
const W = 900, H = 540;

function loadImage(file) {
  const buf = fs.readFileSync(file);
  if (file.endsWith('.png')) {
    const png = PNG.sync.read(buf);
    return { width: png.width, height: png.height, data: png.data };
  }
  const jpg = jpeg.decode(buf, { useTArray: true });
  return { width: jpg.width, height: jpg.height, data: jpg.data };
}

function resizeNearest(img, targetW, targetH) {
  const out = new Uint8Array(targetW * targetH * 4);
  for (let y = 0; y < targetH; y++) {
    const sy = Math.min(img.height - 1, Math.floor(y * img.height / targetH));
    for (let x = 0; x < targetW; x++) {
      const sx = Math.min(img.width - 1, Math.floor(x * img.width / targetW));
      const si = (sy * img.width + sx) * 4;
      const di = (y * targetW + x) * 4;
      out[di] = img.data[si];
      out[di + 1] = img.data[si + 1];
      out[di + 2] = img.data[si + 2];
      out[di + 3] = 255;
    }
  }
  return { width: targetW, height: targetH, data: out };
}

function fitOnCanvas(img, W, H) {
  const scale = Math.min(W / img.width, H / img.height);
  const w = Math.max(1, Math.floor(img.width * scale));
  const h = Math.max(1, Math.floor(img.height * scale));
  const resized = resizeNearest(img, w, h);
  const out = new Uint8Array(W * H * 4);
  // white background
  for (let i = 0; i < out.length; i += 4) {
    out[i] = 255; out[i+1] = 255; out[i+2] = 255; out[i+3] = 255;
  }
  const ox = Math.floor((W - w) / 2), oy = Math.floor((H - h) / 2);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const si = (y * w + x) * 4;
      const di = ((oy + y) * W + (ox + x)) * 4;
      out[di] = resized.data[si];
      out[di+1] = resized.data[si+1];
      out[di+2] = resized.data[si+2];
      out[di+3] = 255;
    }
  }
  return out;
}

function drawRect(buf, x, y, w, h, color) {
  for (let yy = y; yy < y + h; yy++) {
    for (let xx = x; xx < x + w; xx++) {
      if (xx < 0 || yy < 0 || xx >= W || yy >= H) continue;
      const i = (yy * W + xx) * 4;
      buf[i] = color[0]; buf[i+1] = color[1]; buf[i+2] = color[2]; buf[i+3] = 255;
    }
  }
}

// tiny 5x7 bitmap font for needed chars
const FONT = {
  'A':['01110','10001','10001','11111','10001','10001','10001'],
  'B':['11110','10001','11110','10001','10001','10001','11110'],
  'C':['01111','10000','10000','10000','10000','10000','01111'],
  'D':['11110','10001','10001','10001','10001','10001','11110'],
  'E':['11111','10000','11110','10000','10000','10000','11111'],
  'G':['01111','10000','10000','10111','10001','10001','01111'],
  'H':['10001','10001','11111','10001','10001','10001','10001'],
  'I':['11111','00100','00100','00100','00100','00100','11111'],
  'J':['00111','00010','00010','00010','10010','10010','01100'],
  'M':['10001','11011','10101','10101','10001','10001','10001'],
  'O':['01110','10001','10001','10001','10001','10001','01110'],
  'P':['11110','10001','10001','11110','10000','10000','10000'],
  'R':['11110','10001','10001','11110','10100','10010','10001'],
  'S':['01111','10000','10000','01110','00001','00001','11110'],
  'T':['11111','00100','00100','00100','00100','00100','00100'],
  'V':['10001','10001','10001','10001','10001','01010','00100'],
  'X':['10001','10001','01010','00100','01010','10001','10001'],
  'Y':['10001','10001','01010','00100','00100','00100','00100'],
  'b':['10000','10000','11110','10001','10001','10001','11110'],
  'c':['00000','00000','01110','10000','10000','10000','01110'],
  'd':['00001','00001','01111','10001','10001','10001','01111'],
  'e':['00000','00000','01110','10001','11111','10000','01111'],
  'g':['00000','01111','10001','10001','01111','00001','01110'],
  'h':['10000','10000','11110','10001','10001','10001','10001'],
  'i':['00100','00000','01100','00100','00100','00100','01110'],
  'j':['00010','00000','00110','00010','00010','10010','01100'],
  'l':['01100','00100','00100','00100','00100','00100','01110'],
  'm':['00000','00000','11010','10101','10101','10101','10101'],
  'n':['00000','00000','11110','10001','10001','10001','10001'],
  'o':['00000','00000','01110','10001','10001','10001','01110'],
  'p':['00000','00000','11110','10001','10001','11110','10000'],
  'r':['00000','00000','10110','11001','10000','10000','10000'],
  's':['00000','00000','01111','10000','01110','00001','11110'],
  't':['00100','00100','11111','00100','00100','00100','00011'],
  'u':['00000','00000','10001','10001','10001','10011','01101'],
  'v':['00000','00000','10001','10001','10001','01010','00100'],
  'w':['00000','00000','10001','10101','10101','10101','01010'],
  'x':['00000','00000','10001','01010','00100','01010','10001'],
  'y':['00000','00000','10001','10001','01111','00001','01110'],
  'z':['00000','00000','11111','00010','00100','01000','11111'],
  '1':['00100','01100','00100','00100','00100','00100','01110'],
  '2':['01110','10001','00001','00010','00100','01000','11111'],
  '3':['11110','00001','00001','01110','00001','00001','11110'],
  '.':['00000','00000','00000','00000','00000','01100','01100'],
  ' ':['00000','00000','00000','00000','00000','00000','00000'],
};

function drawText(buf, x, y, text, color=[255,255,255]) {
  let cx = x;
  for (const ch of text) {
    const glyph = FONT[ch] || FONT[' '];
    for (let gy=0; gy<glyph.length; gy++) {
      for (let gx=0; gx<glyph[gy].length; gx++) {
        if (glyph[gy][gx] === '1') {
          drawRect(buf, cx + gx*2, y + gy*2, 2, 2, color);
        }
      }
    }
    cx += 12;
  }
}

const enc = GIFEncoder();
for (let idx = 0; idx < files.length; idx++) {
  const img = loadImage(files[idx]);
  const frame = fitOnCanvas(img, W, H);
  drawRect(frame, 20, 20, 430, 46, [0,0,0]);
  drawText(frame, 40, 34, labels[idx]);
  const palette = quantize(frame, 256);
  const index = applyPalette(frame, palette);
  for (let hold = 0; hold < 8; hold++) {
    enc.writeFrame(index, W, H, { palette, delay: 45, repeat: 0 });
  }
}
enc.finish();
fs.writeFileSync(outPath, Buffer.from(enc.bytes()));
console.log(outPath);
