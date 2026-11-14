"""Compile every Pages inline Python smoke test before production deployment."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
class PagesSmokeSyntax(unittest.TestCase):
    def test_embedded_python_heredocs_compile(self):
        yml=(ROOT/".github/workflows/tw-stock-pages.yml").read_text("utf-8")
        lines=yml.splitlines()
        found=0
        for i,line in enumerate(lines):
            if line.strip() not in ("python - <<'PY'","python3 - <<'PY'"):
                continue
            indent=line[:len(line)-len(line.lstrip())]
            statements=[]
            for later in lines[i+1:]:
                if later.strip()=="PY" and later.startswith(indent):
                    break
                self.assertTrue(later.startswith(indent),"Unexpected inline script indentation")
                statements.append(later[len(indent):])
            else:
                self.fail("Unclosed Pages inline Python heredoc")
            compile("\n".join(statements),f"tw-stock-pages.yml script {i+1}","exec")
            found+=1
        self.assertGreaterEqual(found,5)
if __name__=="__main__":
    unittest.main()
