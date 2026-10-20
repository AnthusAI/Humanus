# Limatus is now Humanus

Limatus was renamed to [Humanus](https://pypi.org/project/humanus/). This
package only installs `humanus` and makes `import limatus` and the `limatus`
command use it, with a deprecation warning. Switch to:

```bash
pip install humanus
```

and replace `import limatus` with `import humanus` and the `limatus` command
with `humanus`.
