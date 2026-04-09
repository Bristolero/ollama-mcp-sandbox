export function formatResult(rows, rowCount) {
  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(
          {
            rowCount,
            rows
          },
          null,
          2
        )
      }
    ]
  };
}

export function formatTextResult(text) {
  return {
    content: [
      {
        type: "text",
        text
      }
    ]
  };
}
