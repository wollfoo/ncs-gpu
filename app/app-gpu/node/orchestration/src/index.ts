export function sayHello(name: string): string {
  return `hello, ${name}`;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  // eslint-disable-next-line no-console
  console.log(sayHello('scheduler'));
}
