// P55 用。評価役の答えがぶれる状況を、費用なしで作る呼び先。呼ばれた順に A A B A A A B A A A ... と返す(ぶれ率 20%)。
let n = 0;
const seq = ['A', 'A', 'B', 'A', 'A', 'A', 'B', 'A', 'A', 'A'];
module.exports = class {
  id() { return 'flaky-judge'; }
  async callApi() {
    const a = seq[n++ % seq.length];
    return { output: JSON.stringify({ answer: a }) };
  }
};
