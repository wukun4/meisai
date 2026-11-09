"""Compatibility entry point: current venue verification (no legacy frontiers)."""
import json
from run_venues import ROOT,verify

if __name__=='__main__':
    checks=verify(json.loads((ROOT/'results.json').read_text()))
    print(json.dumps({'checks':len(checks),'all_passed':all(checks.values())},indent=2))
