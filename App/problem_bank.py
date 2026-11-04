"""Built-in pool of daily problems.

Each problem lists test *inputs* only; expected outputs are produced by running the
reference solution, so a problem can never ship with a wrong answer key.
"""

import random


def _rng(seed):
    return random.Random(seed)


def _rand_list(seed, n, lo=-10_000, hi=10_000):
    r = _rng(seed)
    return [r.randint(lo, hi) for _ in range(n)]


def _rand_str(seed, n, alphabet="abcdefghijklmnopqrstuvwxyz"):
    r = _rng(seed)
    return "".join(r.choice(alphabet) for _ in range(n))


def _two_sum_perf():
    nums = _rand_list(1, 6000, 0, 10**6)
    nums = [n * 2 for n in nums]  # all even, so the only odd pair sum is our planted one
    nums[4000] = 1
    nums[5999] = 2
    return [nums, 3]


def _grid(seed, size):
    r = _rng(seed)
    return [["1" if r.random() < 0.45 else "0" for _ in range(size)] for _ in range(size)]


def _intervals(seed, n):
    r = _rng(seed)
    out = []
    for _ in range(n):
        a = r.randint(0, 10**6)
        out.append([a, a + r.randint(0, 500)])
    return out


PROBLEMS = [
    {
        "slug": "two-sum",
        "title": "Two Sum",
        "difficulty": "easy",
        "function_name": "two_sum",
        "params": "nums, target",
        "description": (
            "Given a list of integers `nums` and an integer `target`, return the indices `[i, j]` "
            "(with `i < j`) of the two numbers that add up to `target`.\n\n"
            "Exactly one valid pair exists."
        ),
        "constraints": "2 ≤ len(nums) ≤ 10⁴\nEach input has exactly one answer.",
        "reference_python": (
            "def two_sum(nums, target):\n"
            "    seen = {}\n"
            "    for i, n in enumerate(nums):\n"
            "        if target - n in seen:\n"
            "            return [seen[target - n], i]\n"
            "        seen[n] = i\n"
        ),
        "reference_javascript": (
            "function twoSum(nums, target) {\n"
            "  const seen = new Map();\n"
            "  for (let i = 0; i < nums.length; i++) {\n"
            "    if (seen.has(target - nums[i])) return [seen.get(target - nums[i]), i];\n"
            "    seen.set(nums[i], i);\n"
            "  }\n"
            "}\n"
        ),
        "examples": [[[2, 7, 11, 15], 9], [[3, 2, 4], 6]],
        "hidden": [[[3, 3], 6], [[-1, -2, -3, -4, -5], -8], [[0, 4, 3, 0], 0], [[1, 5, 9, 14], 23]],
        "performance": [_two_sum_perf()],
        "hints": [
            "A brute force double loop works, but it is O(n²). Can you do it in one pass?",
            "For each number, the partner you need is `target - n`. How can you check whether you've already seen it in O(1)?",
            "Store each value's index in a dictionary as you go.",
        ],
        "explanation": "Keep a dictionary from value → index. For every element check whether `target - n` was seen before. One pass, O(n) time, O(n) memory.",
    },
    {
        "slug": "valid-parentheses",
        "title": "Valid Parentheses",
        "difficulty": "easy",
        "function_name": "is_valid",
        "params": "s",
        "description": (
            "Given a string `s` containing only the characters `()[]{}`, return `True` if every bracket "
            "is closed by the same type of bracket in the correct order."
        ),
        "constraints": "0 ≤ len(s) ≤ 10⁵",
        "reference_python": (
            "def is_valid(s):\n"
            "    pairs = {')': '(', ']': '[', '}': '{'}\n"
            "    stack = []\n"
            "    for ch in s:\n"
            "        if ch in pairs:\n"
            "            if not stack or stack.pop() != pairs[ch]:\n"
            "                return False\n"
            "        else:\n"
            "            stack.append(ch)\n"
            "    return not stack\n"
        ),
        "reference_javascript": (
            "function isValid(s) {\n"
            "  const pairs = {')': '(', ']': '[', '}': '{'};\n"
            "  const stack = [];\n"
            "  for (const ch of s) {\n"
            "    if (ch in pairs) { if (stack.pop() !== pairs[ch]) return false; }\n"
            "    else stack.push(ch);\n"
            "  }\n"
            "  return stack.length === 0;\n"
            "}\n"
        ),
        "examples": [["()[]{}"], ["(]"], ["{[]}"]],
        "hidden": [[""], ["(("], ["))"], ["([)]"], ["{[()()]}"], ["]"]],
        "performance": [["([{}])" * 15000]],
        "hints": [
            "The most recently opened bracket must be the first one closed. Which data structure is last-in, first-out?",
            "Push opening brackets onto a stack; on a closing bracket, pop and compare.",
        ],
        "explanation": "Use a stack. Push openers; on a closer, the top of the stack must be its matching opener. The string is valid if the stack is empty at the end.",
    },
    {
        "slug": "fizzbuzz",
        "title": "FizzBuzz Remix",
        "difficulty": "easy",
        "function_name": "fizzbuzz",
        "params": "n",
        "description": (
            "Return a list of strings for the numbers `1..n`. For multiples of 3 use `\"Fizz\"`, "
            "for multiples of 5 use `\"Buzz\"`, for multiples of both use `\"FizzBuzz\"`, otherwise the number itself as a string."
        ),
        "constraints": "1 ≤ n ≤ 10⁵",
        "reference_python": (
            "def fizzbuzz(n):\n"
            "    out = []\n"
            "    for i in range(1, n + 1):\n"
            "        s = ('Fizz' if i % 3 == 0 else '') + ('Buzz' if i % 5 == 0 else '')\n"
            "        out.append(s or str(i))\n"
            "    return out\n"
        ),
        "reference_javascript": (
            "function fizzbuzz(n) {\n"
            "  const out = [];\n"
            "  for (let i = 1; i <= n; i++) out.push(((i % 3 ? '' : 'Fizz') + (i % 5 ? '' : 'Buzz')) || String(i));\n"
            "  return out;\n"
            "}\n"
        ),
        "examples": [[5], [15]],
        "hidden": [[1], [3], [30], [100]],
        "performance": [[50000]],
        "hints": ["Check the 'both' case first, or build the string from two independent checks."],
        "explanation": "Concatenate 'Fizz' when divisible by 3 and 'Buzz' when divisible by 5; fall back to the number when the string is empty.",
    },
    {
        "slug": "max-subarray",
        "title": "Maximum Subarray",
        "difficulty": "medium",
        "function_name": "max_subarray",
        "params": "nums",
        "description": "Return the largest possible sum of a non-empty contiguous slice of `nums`.",
        "constraints": "1 ≤ len(nums) ≤ 10⁵\n-10⁴ ≤ nums[i] ≤ 10⁴",
        "reference_python": (
            "def max_subarray(nums):\n"
            "    best = cur = nums[0]\n"
            "    for n in nums[1:]:\n"
            "        cur = max(n, cur + n)\n"
            "        best = max(best, cur)\n"
            "    return best\n"
        ),
        "reference_javascript": (
            "function maxSubarray(nums) {\n"
            "  let best = nums[0], cur = nums[0];\n"
            "  for (let i = 1; i < nums.length; i++) { cur = Math.max(nums[i], cur + nums[i]); best = Math.max(best, cur); }\n"
            "  return best;\n"
            "}\n"
        ),
        "examples": [[[-2, 1, -3, 4, -1, 2, 1, -5, 4]], [[1]], [[5, 4, -1, 7, 8]]],
        "hidden": [[[-3, -1, -2]], [[0]], [[2, -1, 2, -1, 2]], [[-1, 10, -20, 15]]],
        "performance": [[_rand_list(2, 40000)]],
        "hints": [
            "Checking every slice is O(n²) or worse.",
            "At each index, the best slice ending here either extends the previous best slice or starts fresh.",
            "This is Kadane's algorithm: cur = max(n, cur + n).",
        ],
        "explanation": "Kadane's algorithm: track the best sum of a slice ending at the current index and the best seen overall. O(n) time, O(1) memory.",
    },
    {
        "slug": "longest-unique-substring",
        "title": "Longest Unique Run",
        "difficulty": "medium",
        "function_name": "longest_unique",
        "params": "s",
        "description": "Return the length of the longest substring of `s` that contains no repeated characters.",
        "constraints": "0 ≤ len(s) ≤ 10⁵",
        "reference_python": (
            "def longest_unique(s):\n"
            "    last = {}\n"
            "    start = best = 0\n"
            "    for i, ch in enumerate(s):\n"
            "        if last.get(ch, -1) >= start:\n"
            "            start = last[ch] + 1\n"
            "        last[ch] = i\n"
            "        best = max(best, i - start + 1)\n"
            "    return best\n"
        ),
        "reference_javascript": (
            "function longestUnique(s) {\n"
            "  const last = new Map();\n"
            "  let start = 0, best = 0;\n"
            "  for (let i = 0; i < s.length; i++) {\n"
            "    if (last.has(s[i]) && last.get(s[i]) >= start) start = last.get(s[i]) + 1;\n"
            "    last.set(s[i], i);\n"
            "    best = Math.max(best, i - start + 1);\n"
            "  }\n"
            "  return best;\n"
            "}\n"
        ),
        "examples": [["abcabcbb"], ["bbbbb"], ["pwwkew"]],
        "hidden": [[""], ["a"], ["abba"], ["dvdf"], ["tmmzuxt"]],
        "performance": [[_rand_str(3, 60000)]],
        "hints": [
            "Think of a window [start, i] that always contains unique characters.",
            "When you meet a repeated character, jump `start` just past its previous position.",
        ],
        "explanation": "Sliding window: remember each character's last index. When a repeat falls inside the window, move the window start past it. O(n).",
    },
    {
        "slug": "merge-intervals",
        "title": "Merge Intervals",
        "difficulty": "medium",
        "function_name": "merge_intervals",
        "params": "intervals",
        "description": (
            "Given a list of `[start, end]` intervals, merge all overlapping intervals (touching counts as overlapping) "
            "and return them sorted by start."
        ),
        "constraints": "0 ≤ len(intervals) ≤ 10⁴",
        "reference_python": (
            "def merge_intervals(intervals):\n"
            "    out = []\n"
            "    for s, e in sorted(intervals):\n"
            "        if out and s <= out[-1][1]:\n"
            "            out[-1][1] = max(out[-1][1], e)\n"
            "        else:\n"
            "            out.append([s, e])\n"
            "    return out\n"
        ),
        "reference_javascript": (
            "function mergeIntervals(intervals) {\n"
            "  const out = [];\n"
            "  for (const [s, e] of [...intervals].sort((a, b) => a[0] - b[0] || a[1] - b[1])) {\n"
            "    if (out.length && s <= out[out.length - 1][1]) out[out.length - 1][1] = Math.max(out[out.length - 1][1], e);\n"
            "    else out.push([s, e]);\n"
            "  }\n"
            "  return out;\n"
            "}\n"
        ),
        "examples": [[[[1, 3], [2, 6], [8, 10], [15, 18]]], [[[1, 4], [4, 5]]]],
        "hidden": [[[]], [[[5, 7]]], [[[6, 8], [1, 9], [2, 4]]], [[[1, 2], [3, 4]]]],
        "performance": [[_intervals(4, 8000)]],
        "hints": ["Sort by start first.", "Walk the sorted list; either extend the last merged interval or start a new one."],
        "explanation": "Sort by start, then sweep, extending the last merged interval while the next one starts before it ends. O(n log n).",
    },
    {
        "slug": "count-islands",
        "title": "Count the Islands",
        "difficulty": "medium",
        "function_name": "count_islands",
        "params": "grid",
        "description": (
            "`grid` is a 2D list of `\"1\"` (land) and `\"0\"` (water). Return the number of islands — groups of land "
            "connected horizontally or vertically."
        ),
        "constraints": "0 ≤ rows, cols ≤ 300",
        "reference_python": (
            "def count_islands(grid):\n"
            "    if not grid:\n"
            "        return 0\n"
            "    rows, cols = len(grid), len(grid[0])\n"
            "    seen = [[False] * cols for _ in range(rows)]\n"
            "    count = 0\n"
            "    for r in range(rows):\n"
            "        for c in range(cols):\n"
            "            if grid[r][c] == '1' and not seen[r][c]:\n"
            "                count += 1\n"
            "                stack = [(r, c)]\n"
            "                seen[r][c] = True\n"
            "                while stack:\n"
            "                    y, x = stack.pop()\n"
            "                    for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):\n"
            "                        if 0 <= ny < rows and 0 <= nx < cols and grid[ny][nx] == '1' and not seen[ny][nx]:\n"
            "                            seen[ny][nx] = True\n"
            "                            stack.append((ny, nx))\n"
            "    return count\n"
        ),
        "reference_javascript": (
            "function countIslands(grid) {\n"
            "  if (!grid.length) return 0;\n"
            "  const R = grid.length, C = grid[0].length;\n"
            "  const seen = Array.from({length: R}, () => new Array(C).fill(false));\n"
            "  let count = 0;\n"
            "  for (let r = 0; r < R; r++) for (let c = 0; c < C; c++) {\n"
            "    if (grid[r][c] !== '1' || seen[r][c]) continue;\n"
            "    count++; seen[r][c] = true; const stack = [[r, c]];\n"
            "    while (stack.length) {\n"
            "      const [y, x] = stack.pop();\n"
            "      for (const [ny, nx] of [[y+1,x],[y-1,x],[y,x+1],[y,x-1]]) {\n"
            "        if (ny >= 0 && ny < R && nx >= 0 && nx < C && grid[ny][nx] === '1' && !seen[ny][nx]) { seen[ny][nx] = true; stack.push([ny, nx]); }\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "  return count;\n"
            "}\n"
        ),
        "examples": [
            [[["1", "1", "0", "0"], ["1", "0", "0", "1"], ["0", "0", "1", "1"]]],
            [[["1", "1", "1"], ["0", "1", "0"], ["1", "1", "1"]]],
        ],
        "hidden": [[[]], [[["0"]]], [[["1"]]], [[["1", "0", "1", "0", "1"]]]],
        "performance": [[_grid(5, 200)]],
        "hints": [
            "Every time you find unvisited land, you've found a new island.",
            "From that cell, flood-fill (DFS/BFS) to mark the whole island as visited.",
            "Deep recursion can overflow on big grids — an explicit stack is safer.",
        ],
        "explanation": "Scan every cell; on unvisited land, increment the count and flood-fill its island with an explicit stack. O(rows × cols).",
    },
    {
        "slug": "roman-to-integer",
        "title": "Roman Numerals",
        "difficulty": "easy",
        "function_name": "roman_to_int",
        "params": "s",
        "description": "Convert the Roman numeral `s` to an integer. Subtractive forms like `IV`, `IX`, `XL`, `XC`, `CD` and `CM` are used.",
        "constraints": "1 ≤ value ≤ 3999",
        "reference_python": (
            "def roman_to_int(s):\n"
            "    v = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}\n"
            "    total = 0\n"
            "    for i, ch in enumerate(s):\n"
            "        if i + 1 < len(s) and v[ch] < v[s[i + 1]]:\n"
            "            total -= v[ch]\n"
            "        else:\n"
            "            total += v[ch]\n"
            "    return total\n"
        ),
        "reference_javascript": (
            "function romanToInt(s) {\n"
            "  const v = {I: 1, V: 5, X: 10, L: 50, C: 100, D: 500, M: 1000};\n"
            "  let total = 0;\n"
            "  for (let i = 0; i < s.length; i++) total += (i + 1 < s.length && v[s[i]] < v[s[i + 1]]) ? -v[s[i]] : v[s[i]];\n"
            "  return total;\n"
            "}\n"
        ),
        "examples": [["III"], ["LVIII"], ["MCMXCIV"]],
        "hidden": [["IV"], ["IX"], ["XL"], ["MMMCMXCIX"], ["CDXLIV"]],
        "performance": [],
        "hints": ["If a symbol is smaller than the one after it, it is subtracted."],
        "explanation": "Walk left to right; subtract a value when the next symbol is larger, otherwise add it.",
    },
    {
        "slug": "product-except-self",
        "title": "Product of the Others",
        "difficulty": "medium",
        "function_name": "product_except_self",
        "params": "nums",
        "description": "Return a list where element `i` is the product of every element of `nums` except `nums[i]`. Do it without division.",
        "constraints": "2 ≤ len(nums) ≤ 10⁵\nAll products fit in a 32-bit integer.",
        "reference_python": (
            "def product_except_self(nums):\n"
            "    n = len(nums)\n"
            "    out = [1] * n\n"
            "    left = 1\n"
            "    for i in range(n):\n"
            "        out[i] = left\n"
            "        left *= nums[i]\n"
            "    right = 1\n"
            "    for i in range(n - 1, -1, -1):\n"
            "        out[i] *= right\n"
            "        right *= nums[i]\n"
            "    return out\n"
        ),
        "reference_javascript": (
            "function productExceptSelf(nums) {\n"
            "  const n = nums.length, out = new Array(n).fill(1);\n"
            "  let left = 1, right = 1;\n"
            "  for (let i = 0; i < n; i++) { out[i] = left; left *= nums[i]; }\n"
            "  for (let i = n - 1; i >= 0; i--) { out[i] *= right; right *= nums[i]; }\n"
            "  return out;\n"
            "}\n"
        ),
        "examples": [[[1, 2, 3, 4]], [[-1, 1, 0, -3, 3]]],
        "hidden": [[[2, 3]], [[0, 0]], [[5, 0, 2]], [[1, 1, 1, 1]]],
        "performance": [[[1 if i % 7 else -1 for i in range(30000)]]],
        "hints": [
            "The answer at i = (product of everything left of i) × (product of everything right of i).",
            "Build prefix products in one pass and suffix products in a second pass.",
        ],
        "explanation": "Two passes: prefix products left-to-right, then multiply by suffix products right-to-left. O(n), O(1) extra memory.",
    },
    {
        "slug": "longest-common-prefix",
        "title": "Common Prefix",
        "difficulty": "easy",
        "function_name": "common_prefix",
        "params": "words",
        "description": "Return the longest string that is a prefix of every word in `words` (empty string if none).",
        "constraints": "1 ≤ len(words) ≤ 200",
        "reference_python": (
            "def common_prefix(words):\n"
            "    prefix = min(words)\n"
            "    last = max(words)\n"
            "    i = 0\n"
            "    while i < len(prefix) and prefix[i] == last[i]:\n"
            "        i += 1\n"
            "    return prefix[:i]\n"
        ),
        "reference_javascript": (
            "function commonPrefix(words) {\n"
            "  let p = words[0];\n"
            "  for (const w of words) while (!w.startsWith(p)) p = p.slice(0, -1);\n"
            "  return p;\n"
            "}\n"
        ),
        "examples": [[["flower", "flow", "flight"]], [["dog", "racecar", "car"]]],
        "hidden": [[["alone"]], [["", "b"]], [["abc", "abc"]], [["ab", "a"]]],
        "performance": [],
        "hints": ["The prefix can never be longer than the shortest word.", "Compare character by character across all words."],
        "explanation": "Compare columns of characters until one differs. Trick: only the lexicographically smallest and largest words need comparing.",
    },
    {
        "slug": "climbing-stairs",
        "title": "Stair Climber",
        "difficulty": "easy",
        "function_name": "climb_stairs",
        "params": "n",
        "description": "You can climb 1 or 2 steps at a time. In how many distinct ways can you climb a staircase of `n` steps?",
        "constraints": "1 ≤ n ≤ 45",
        "reference_python": (
            "def climb_stairs(n):\n"
            "    a, b = 1, 1\n"
            "    for _ in range(n):\n"
            "        a, b = b, a + b\n"
            "    return a\n"
        ),
        "reference_javascript": (
            "function climbStairs(n) {\n"
            "  let a = 1, b = 1;\n"
            "  for (let i = 0; i < n; i++) [a, b] = [b, a + b];\n"
            "  return a;\n"
            "}\n"
        ),
        "examples": [[2], [3]],
        "hidden": [[1], [5], [10], [30]],
        "performance": [[45]],
        "hints": [
            "To reach step n you came from step n-1 or step n-2.",
            "That's the Fibonacci recurrence — plain recursion is exponential, so remember previous answers.",
        ],
        "explanation": "ways(n) = ways(n-1) + ways(n-2), i.e. Fibonacci. Iterate with two variables for O(n) time and O(1) memory.",
    },
    {
        "slug": "binary-search",
        "title": "Needle in a Sorted Haystack",
        "difficulty": "easy",
        "function_name": "find_index",
        "params": "nums, target",
        "description": "`nums` is sorted ascending with distinct values. Return the index of `target`, or `-1` if it is absent.",
        "constraints": "0 ≤ len(nums) ≤ 10⁶",
        "reference_python": (
            "def find_index(nums, target):\n"
            "    lo, hi = 0, len(nums) - 1\n"
            "    while lo <= hi:\n"
            "        mid = (lo + hi) // 2\n"
            "        if nums[mid] == target:\n"
            "            return mid\n"
            "        if nums[mid] < target:\n"
            "            lo = mid + 1\n"
            "        else:\n"
            "            hi = mid - 1\n"
            "    return -1\n"
        ),
        "reference_javascript": (
            "function findIndex(nums, target) {\n"
            "  let lo = 0, hi = nums.length - 1;\n"
            "  while (lo <= hi) {\n"
            "    const mid = (lo + hi) >> 1;\n"
            "    if (nums[mid] === target) return mid;\n"
            "    if (nums[mid] < target) lo = mid + 1; else hi = mid - 1;\n"
            "  }\n"
            "  return -1;\n"
            "}\n"
        ),
        "examples": [[[-1, 0, 3, 5, 9, 12], 9], [[-1, 0, 3, 5, 9, 12], 2]],
        "hidden": [[[], 1], [[5], 5], [[1, 2], 2], [[1, 3, 5, 7], 0], [[1, 3, 5, 7], 8]],
        "performance": [[list(range(0, 400000, 2)), 399998]],
        "hints": ["The list is sorted — you can throw away half of it with one comparison."],
        "explanation": "Classic binary search: halve the search range each step. O(log n).",
    },
    {
        "slug": "coin-change",
        "title": "Fewest Coins",
        "difficulty": "hard",
        "function_name": "coin_change",
        "params": "coins, amount",
        "description": "Return the fewest coins (unlimited supply of each denomination in `coins`) that sum to `amount`, or `-1` if impossible.",
        "constraints": "1 ≤ len(coins) ≤ 12\n0 ≤ amount ≤ 10⁴",
        "reference_python": (
            "def coin_change(coins, amount):\n"
            "    INF = amount + 1\n"
            "    best = [0] + [INF] * amount\n"
            "    for a in range(1, amount + 1):\n"
            "        for c in coins:\n"
            "            if c <= a and best[a - c] + 1 < best[a]:\n"
            "                best[a] = best[a - c] + 1\n"
            "    return best[amount] if best[amount] != INF else -1\n"
        ),
        "reference_javascript": (
            "function coinChange(coins, amount) {\n"
            "  const INF = amount + 1, best = new Array(amount + 1).fill(INF);\n"
            "  best[0] = 0;\n"
            "  for (let a = 1; a <= amount; a++) for (const c of coins) if (c <= a && best[a - c] + 1 < best[a]) best[a] = best[a - c] + 1;\n"
            "  return best[amount] === INF ? -1 : best[amount];\n"
            "}\n"
        ),
        "examples": [[[1, 2, 5], 11], [[2], 3], [[1], 0]],
        "hidden": [[[186, 419, 83, 408], 6249], [[2, 5, 10, 1], 27], [[3, 7], 5], [[1, 3, 4], 6]],
        "performance": [[[1, 7, 23, 51, 97, 211], 9999]],
        "hints": [
            "Greedy (always take the biggest coin) fails for coins like [1, 3, 4] and amount 6.",
            "Let best[a] be the fewest coins for amount a. How does best[a] relate to best[a - c]?",
            "Fill best[0..amount] bottom-up.",
        ],
        "explanation": "Bottom-up DP: best[a] = 1 + min(best[a - c]) over coins c ≤ a. O(amount × len(coins)).",
    },
    {
        "slug": "spiral-order",
        "title": "Spiral Walk",
        "difficulty": "hard",
        "function_name": "spiral_order",
        "params": "matrix",
        "description": "Return all elements of the `m × n` `matrix` in clockwise spiral order, starting at the top-left.",
        "constraints": "0 ≤ m, n ≤ 100",
        "reference_python": (
            "def spiral_order(matrix):\n"
            "    out = []\n"
            "    while matrix:\n"
            "        out += matrix.pop(0)\n"
            "        matrix = [list(row) for row in zip(*matrix)][::-1]\n"
            "    return out\n"
        ),
        "reference_javascript": (
            "function spiralOrder(matrix) {\n"
            "  const out = [];\n"
            "  if (!matrix.length) return out;\n"
            "  let top = 0, bottom = matrix.length - 1, left = 0, right = matrix[0].length - 1;\n"
            "  while (top <= bottom && left <= right) {\n"
            "    for (let c = left; c <= right; c++) out.push(matrix[top][c]);\n"
            "    for (let r = top + 1; r <= bottom; r++) out.push(matrix[r][right]);\n"
            "    if (top < bottom) for (let c = right - 1; c >= left; c--) out.push(matrix[bottom][c]);\n"
            "    if (left < right) for (let r = bottom - 1; r > top; r--) out.push(matrix[r][left]);\n"
            "    top++; bottom--; left++; right--;\n"
            "  }\n"
            "  return out;\n"
            "}\n"
        ),
        "examples": [[[[1, 2, 3], [4, 5, 6], [7, 8, 9]]], [[[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]]],
        "hidden": [[[]], [[[1]]], [[[1, 2]]], [[[1], [2], [3]]], [[[1, 2], [3, 4], [5, 6]]]],
        "performance": [],
        "hints": [
            "Keep four boundaries: top, bottom, left, right.",
            "Walk right, down, left, up — shrinking a boundary after each side. Watch out for single rows/columns.",
        ],
        "explanation": "Maintain four shrinking boundaries and walk each side in turn, guarding against re-visiting a single remaining row or column.",
    },
]


def problem_for_date(day):
    return PROBLEMS[day.toordinal() % len(PROBLEMS)]
