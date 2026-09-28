export default {
  extends: ["@commitlint/config-conventional"],
  // GitHub-generated merge commits are not conventional; skip them.
  ignores: [(message) => message.startsWith("Merge ")],
  rules: {
    // Release/tooling commit bodies can contain long URLs and lines.
    "body-max-line-length": [0, "always", 100],
  },
};
