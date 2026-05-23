"""
Entry point for the dropshipping pipeline.

Usage:
    python main.py "ergonomic keyboard"
    python main.py "ergonomic keyboard" --image-gen   # also run DALL-E
    python main.py --help
"""

import argparse
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    parser = argparse.ArgumentParser(description="AI dropshipping pipeline")
    parser.add_argument("product", help="Product name to evaluate, e.g. 'ergonomic keyboard'")
    parser.add_argument(
        "--image-gen",
        action="store_true",
        help="Call DALL-E 3 to generate a hero product image (requires OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--image-url",
        default=None,
        help="Pre-scraped product image URL to pass to Claude vision",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Print full store config as JSON instead of summary",
    )
    args = parser.parse_args()

    from agents.orchestrator import run_pipeline

    # Minimal nimble_data stub so orchestrator can pass image_url downstream
    nimble_data = {"image_url": args.image_url} if args.image_url else None

    # Patch generate_image flag into orchestrator call
    if args.image_gen:
        import agents.orchestrator as orch
        _orig = orch.run_pipeline

        def _patched(product_name, nimble_data=None):
            # Re-implement just enough to flip the flag
            import agents.advertising as adv_mod
            _orig_run = adv_mod.run_advertising_agent

            def _wrapped(*a, **kw):
                kw["generate_image"] = True
                return _orig_run(*a, **kw)

            adv_mod.run_advertising_agent = _wrapped
            result = _orig(product_name, nimble_data=nimble_data)
            adv_mod.run_advertising_agent = _orig_run
            return result

        result = _patched(args.product, nimble_data=nimble_data)
    else:
        result = run_pipeline(args.product, nimble_data=nimble_data)

    if "error" in result:
        print(f"\n❌  Pipeline halted at [{result['stage']}]: {result['error']}")
        sys.exit(1)

    if args.output_json:
        # Strip internal _debug keys for clean output
        clean = {k: v for k, v in result.items() if not k.startswith("_")}
        print(json.dumps(clean, indent=2, default=str))
    else:
        print(f"""
Store launched
──────────────────────────────────────
URL:        {result['store_url']}
Product:    {result['product_name']}
Tagline:    {result['tagline']}
Price:      ${result['price']:.2f}
Supplier:   {result['supplier']}
Legal:      {result['legal_risk_level']} risk
Hero image: {result['hero_image_url'] or '(none)'}
SEO:        {', '.join(result['seo_keywords'][:4])}
""")


if __name__ == "__main__":
    main()
