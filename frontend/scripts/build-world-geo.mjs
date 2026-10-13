// 用法：node scripts/build-world-geo.mjs <原始 ne_110m geojson> [输出路径]
// 产出的 properties.name = 地区 code，供 ECharts 按 code 着色；
// 与后端 app/core/geo.py 的一致性由 backend/tests/test_geo_asset.py 守护。
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

const [, , source, target = "src/assets/world.geo.json"] = process.argv;
if (!source) {
  console.error("用法：node scripts/build-world-geo.mjs <原始 geojson> [输出路径]");
  process.exit(1);
}

const round = (value) => Math.round(value * 100) / 100;
const roundCoords = (node) =>
  Array.isArray(node[0]) ? node.map(roundCoords) : [round(node[0]), round(node[1])];

const raw = JSON.parse(readFileSync(source, "utf-8"));
const features = raw.features
  .map((feature) => {
    const props = feature.properties ?? {};
    // ISO_A2 在 Natural Earth 里对法国/挪威等是 "-99"，优先用 ISO_A2_EH
    const code = String(props.ISO_A2_EH ?? props.ISO_A2 ?? "").toLowerCase();
    if (!/^[a-z]{2}$/.test(code)) return null;
    return {
      type: "Feature",
      properties: { name: code, name_zh: props.NAME_ZH ?? "" },
      geometry: {
        type: feature.geometry.type,
        coordinates: roundCoords(feature.geometry.coordinates),
      },
    };
  })
  .filter(Boolean);

mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, JSON.stringify({ type: "FeatureCollection", features }));
console.log(`写出 ${features.length} 个国家的边界 → ${target}`);
