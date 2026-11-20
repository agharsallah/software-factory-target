# software-factory-target

Target repository for the software factory.

- `factory-bot` pushes branches and opens pull requests.
- `factory-merger` merges a pull request only when the required check `factory-gates` is green.
- Humans approve with `/approve` comments or PR reviews, verified by GitHub account id.

Add the repo's real checks to `gates.sh` (or a `gates` make target); `.github/workflows/factory-gates.yml` runs it.
