from pathlib import Path
import re
import urllib.request

APP_STORE_URL = "https://apps.apple.com/de/app/maengelfix/id6801253878"
BADGE_URL = "https://tools.applemediaservices.com/api/badges/download-on-the-app-store/black/de-de?size=250x83"
FALLBACK_BADGE_URL = "https://developer.apple.com/assets/elements/badges/download-on-the-app-store.svg"

root = Path(__file__).resolve().parents[1]
app_path = root / "client/src/App.jsx"
css_path = root / "client/src/maengelfix-pro.css"
badge_dir = root / "client/public/badges"
badge_dir.mkdir(parents=True, exist_ok=True)


def download_badge():
    last_error = None
    for url in (BADGE_URL, FALLBACK_BADGE_URL):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 MängelFix/1.0"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
            head = data[:2048].lstrip().lower()
            if b"<svg" in head or head.startswith(b"<?xml"):
                path = badge_dir / "app-store-de.svg"
            elif data.startswith(b"\x89PNG\r\n\x1a\n"):
                path = badge_dir / "app-store-de.png"
            elif data[:3] == b"\xff\xd8\xff":
                path = badge_dir / "app-store-de.jpg"
            else:
                raise RuntimeError(f"Unexpected Apple badge payload from {url}")
            path.write_bytes(data)
            for other in badge_dir.glob("app-store-de.*"):
                if other != path:
                    other.unlink()
            print(f"Apple badge saved locally as {path.relative_to(root)}")
            return "/badges/" + path.name
        except Exception as exc:
            last_error = exc
            print(f"Badge download failed for {url}: {exc}")
    raise RuntimeError(f"Unable to download official Apple badge: {last_error}")


badge_src = download_badge()

s = app_path.read_text(encoding="utf-8")

if 'className="heroStoreCta"' not in s:
    hero_start = s.index('            <div className="heroActions">')
    trust_start = s.index('            <div className="heroTrust">', hero_start)
    hero_chunk = s[hero_start:trust_start]

    badge_anchor = re.compile(
        r'\n\s*<a\s+href="https://apps\.apple\.com/de/app/maengelfix/id6801253878".*?</a>',
        re.DOTALL,
    )
    hero_chunk, count = badge_anchor.subn('', hero_chunk, count=1)
    if count != 1:
        raise SystemExit("Current App Store badge anchor not found inside heroActions")

    store_cta = f'''            <div className="heroStoreCta" aria-label="MängelFix für iPhone und iPad">
              <div className="heroStoreCopy">
                <strong>Auch als App</strong>
                <span>Für iPhone und iPad</span>
              </div>
              <a
                className="heroStoreBadge"
                href="{APP_STORE_URL}"
                target="_blank"
                rel="noreferrer"
                aria-label="MängelFix im App Store laden"
              >
                <img src="{badge_src}" alt="Laden im App Store" />
              </a>
            </div>
'''

    s = s[:hero_start] + hero_chunk + store_cta + s[trust_start:]
else:
    s = re.sub(r'src="/badges/app-store-de\.[^"]+"', f'src="{badge_src}"', s, count=1)

app_path.write_text(s, encoding="utf-8")

css = css_path.read_text(encoding="utf-8")
marker = "/* MängelFix v0.28 — App Store hero + mobile hardening */"
if marker not in css:
    css += f'''

{marker}
.landingPage {{ overflow-x: clip; }}
.heroStoreCta {{
  width: fit-content;
  max-width: 100%;
  margin-top: 16px;
  padding: 11px 13px;
  display: flex;
  align-items: center;
  gap: 18px;
  border: 1px solid #dfe4e8;
  border-radius: 10px;
  background: rgba(255,255,255,.82);
  box-shadow: 0 10px 28px rgba(23,32,42,.06);
}}
.heroStoreCopy {{ display: flex; flex-direction: column; gap: 2px; min-width: 118px; }}
.heroStoreCopy strong {{ color: #1d2732; font-size: 13px; line-height: 1.2; }}
.heroStoreCopy span {{ color: #77828d; font-size: 11px; line-height: 1.25; }}
.heroStoreBadge {{ display: inline-flex; align-items: center; line-height: 0; flex: 0 0 auto; }}
.heroStoreBadge img {{ display: block; width: 154px; max-width: 100%; height: auto; }}

@media (max-width: 900px) {{
  .publicHeader {{ gap: 12px; }}
  .publicHeader .brandButton {{ min-width: 0; flex: 1 1 auto; overflow: hidden; }}
  .publicHeader .mfLogoText strong {{ white-space: nowrap; }}
  .publicNav {{ margin-left: auto; flex: 0 0 auto; }}
  .publicNav > button:not(.navPrimary) {{ display: none; }}
  .navPrimary {{ white-space: nowrap; }}
}}

@media (max-width: 620px) {{
  .publicHeader {{ width: calc(100% - 24px); gap: 8px; }}
  .publicHeader .mfLogoMark {{ width: 40px; height: 40px; flex-basis: 40px; }}
  .publicHeader .mfLogoText strong {{ font-size: 17px; }}
  .navPrimary {{ padding: 10px 11px; font-size: 12px; }}

  .landingHero {{ width: calc(100% - 28px); padding-top: 40px; gap: 26px; }}
  .landingEyebrow {{ font-size: 9px; letter-spacing: .13em; line-height: 1.45; }}
  .heroText {{ min-width: 0; }}
  .heroText h1 {{ font-size: clamp(38px, 10.7vw, 44px); line-height: 1.01; letter-spacing: -.052em; }}
  .heroText > p {{ font-size: 16px; line-height: 1.58; }}

  .heroActions {{ flex-direction: column; align-items: stretch; gap: 10px; margin-top: 26px; }}
  .heroActions .landingPrimary,
  .heroActions .landingSecondary {{ width: 100%; min-height: 50px; box-sizing: border-box; }}

  .heroStoreCta {{
    width: 100%;
    box-sizing: border-box;
    justify-content: space-between;
    gap: 12px;
    margin-top: 12px;
    padding: 11px 12px;
  }}
  .heroStoreCopy {{ min-width: 0; }}
  .heroStoreBadge img {{ width: 145px; }}
  .heroTrust {{ margin-top: 22px; gap: 9px 14px; line-height: 1.4; }}

  .heroVisual {{ width: 100%; min-width: 0; overflow: hidden; }}
  .floatingBadge {{ right: 8px; }}
}}
'''
    css_path.write_text(css, encoding="utf-8")

print("MängelFix hero App Store CTA and mobile layout updated")
