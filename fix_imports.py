#!/usr/bin/env python3
"""Fix imports and React namespace usage in page.tsx."""
import sys

PAGE = '/home/adharshaST/HYQUB/frontend/app/page.tsx'

with open(PAGE, 'r', encoding='utf-8') as f:
    src = f.read()

# 1. Add getWalletState to the named imports from '@/lib/api'
OLD_IMPORT = "  verifySignature,\n} from '@/lib/api'"
NEW_IMPORT = "  verifySignature,\n  getWalletState,\n} from '@/lib/api'"

if OLD_IMPORT in src:
    src = src.replace(OLD_IMPORT, NEW_IMPORT, 1)
    print('getWalletState import added.')
elif 'getWalletState' in src.split("from '@/lib/api'")[0]:
    print('getWalletState already imported.')
else:
    print('WARNING: could not find import insertion point.')

# 2. Replace React.useState / React.useEffect with plain hooks
#    (React is not imported as a namespace; useState/useEffect are named imports)
src = src.replace('React.useState<string | null>(null)', 'useState<string | null>(null)')
src = src.replace('React.useState(false)', 'useState(false)')
src = src.replace('React.useEffect(', 'useEffect(')
src = src.replace('React.useState(false)\n', 'useState(false)\n')
src = src.replace("React.useState<string | null>(null)\n", "useState<string | null>(null)\n")

# Also fix AnvilSelector which used React.useState
src = src.replace(
    '  const [showCustom, setShowCustom] = React.useState(false)',
    '  const [showCustom, setShowCustom] = useState(false)'
)
print('React.* namespace references fixed.')

with open(PAGE, 'w', encoding='utf-8') as f:
    f.write(src)

print('Done.')
