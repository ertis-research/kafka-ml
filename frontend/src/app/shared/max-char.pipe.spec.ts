import { MaxCharPipe } from './max-char.pipe';

describe('MaxCharPipe', () => {
  it('create an instance', () => {
    const pipe = new MaxCharPipe();
    expect(pipe).toBeTruthy();
  });
});
