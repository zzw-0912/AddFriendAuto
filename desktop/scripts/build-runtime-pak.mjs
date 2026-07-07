import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const RUNTIME_DIR = path.join(ROOT, "src-tauri", "resources", "friendauto_runtime");
const OUTPUT_FILE = path.join(ROOT, "src-tauri", "resources", "runtime.pak");
const MAGIC = Buffer.from("FARPAK01", "ascii");
const KEY = Buffer.from("71f40eea2fa30553df885db6a24609c9029d4cb54fb6e80da485b92a8f0fe4c7", "hex");

function shouldSkip(fullPath) {
  const name = path.basename(fullPath).toLowerCase();
  return name === "__pycache__" || name.endsWith(".pyo");
}

function collectFiles(dir, base = dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (shouldSkip(fullPath)) continue;
    if (entry.isDirectory()) {
      files.push(...collectFiles(fullPath, base));
    } else if (entry.isFile()) {
      const relativePath = path.relative(base, fullPath).replaceAll(path.sep, "/");
      files.push({ fullPath, relativePath });
    }
  }
  return files.sort((a, b) => a.relativePath.localeCompare(b.relativePath));
}

function u32(value) {
  const buffer = Buffer.allocUnsafe(4);
  buffer.writeUInt32LE(value, 0);
  return buffer;
}

function u64(value) {
  const buffer = Buffer.allocUnsafe(8);
  buffer.writeBigUInt64LE(BigInt(value), 0);
  return buffer;
}

function buildArchive(files) {
  const chunks = [u32(files.length)];
  for (const file of files) {
    const name = Buffer.from(file.relativePath, "utf8");
    const data = fs.readFileSync(file.fullPath);
    chunks.push(u32(name.length), u64(data.length), name, data);
  }
  return Buffer.concat(chunks);
}

if (!fs.existsSync(RUNTIME_DIR)) {
  throw new Error(`runtime source not found: ${RUNTIME_DIR}`);
}

const files = collectFiles(RUNTIME_DIR);
const archive = buildArchive(files);
const compressed = zlib.gzipSync(archive, { level: 9 });
const nonce = crypto.randomBytes(12);
const cipher = crypto.createCipheriv("aes-256-gcm", KEY, nonce);
const encrypted = Buffer.concat([cipher.update(compressed), cipher.final()]);
const tag = cipher.getAuthTag();
const output = Buffer.concat([MAGIC, nonce, tag, encrypted]);

fs.mkdirSync(path.dirname(OUTPUT_FILE), { recursive: true });
fs.writeFileSync(OUTPUT_FILE, output);

const sourceMb = (archive.length / 1024 / 1024).toFixed(2);
const compressedMb = (compressed.length / 1024 / 1024).toFixed(2);
const outputMb = (output.length / 1024 / 1024).toFixed(2);
console.log(`runtime.pak built: files=${files.length} source=${sourceMb}MB gzip=${compressedMb}MB encrypted=${outputMb}MB`);
