# Third-party notices

## ai-writing-tells.yml

The patterns in the `ai-writing-tells` policy pack are adapted from
[avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing) by Conor
Bronsdon, specifically its pattern catalog (`references/patterns.md`) and the
regular expressions in its detector (`detector/patterns.js`). The regexes were
ported to Python `re` syntax and regrouped into Limatus policies. The policy
guidance, rewrite guidance, and examples in the pack were written for Limatus.

avoid-ai-writing is distributed under the MIT License:

```
MIT License

Copyright (c) 2026 Conor Bronsdon

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## asd-ste100.yml

The `asd-ste100` pack implements the writing rules of ASD-STE100 Simplified
Technical English as Limatus checks. ASD-STE100 is a specification of the
AeroSpace, Security and Defence Industries Association of Europe (ASD); its
dictionary of approved words and its examples are licensed by ASD and are not
included. The word lists in the pack are a small synthetic seed written for
Limatus. Organizations that license the specification should replace them with
the official dictionary.

## plain-language.yml

The `plain-language` pack is based on the Federal Plain Language Guidelines
(revision 1, May 2011), published by the Plain Language Action and Information
Network (PLAIN) at plainlanguage.gov and now maintained at
https://digital.gov/guides/plain-language. The guidelines are a work of the
U.S. government and are in the public domain. The word substitutions are drawn
from the guidelines' list of simple words and phrases; the policy guidance and
questions were written for Limatus.
