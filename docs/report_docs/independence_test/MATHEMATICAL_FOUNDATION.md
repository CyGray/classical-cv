# Independence Testing: Mathematical and Statistical Foundation

## 1. Problem Statement

In a verification (1:1 matching) system, a decision function compares a probe image against a stored gallery template and outputs a distance (or similarity) score. An accept-or-reject decision requires a threshold $\tau$ on this score. The central difficulty is picking $\tau$ when:

- The gallery contains only $n$ enrolled identities (typically $n \ll 10^4$).
- No ground-truth negative pairs representing the open-world population are available.
- A threshold tuned on a small validation split generalizes poorly to unseen impostors.

Independence testing addresses this by constructing the empirical impostor distance distribution directly from the gallery itself.

## 2. Formal Model

### Setup

Let $G = \{I_1, I_2, \ldots, I_n\}$ be a gallery of $n$ distinct identities. Each identity $I_i$ contributes exactly one image $x_i$. A feature extractor $f : \mathcal{X} \to \mathbb{R}^d$ maps each preprocessed image to a $d$-dimensional feature vector. A distance metric $\delta : \mathbb{R}^d \times \mathbb{R}^d \to \mathbb{R}_+$ measures dissimilarity between feature vectors.

### Exhaustive Impostor Comparison

For every ordered pair $(i, j)$ with $i \neq j$, compute

$$s_{ij} = \delta(f(x_i), f(x_j)), \qquad i \neq j.$$

Because $i \neq j$ for all pairs, every comparison is an impostor pair by construction. There are

$$M = n(n-1)$$

such ordered comparisons (or $\binom{n}{2} = n(n-1)/2$ unordered pairs). On La Salle DB1 ($n=28$), $M = 756$. On LFW DB1 ($n=5\,749$), $M \approx 33 \times 10^6$.

### Empirical Impostor Distribution

The set $\{s_{ij} : i \neq j\}$ is the *empirical impostor distance distribution*. Its cumulative distribution function is

$$\hat{F}_n(t) = \frac{1}{M} \sum_{i \neq j} \mathbb{1}[s_{ij} \leq t].$$

$\hat{F}_n(t)$ is the fraction of impostor pairs that would be falsely accepted at threshold $t$. It is a consistent estimator of the true impostor CDF $F(t)$ as $n \to \infty$, provided the gallery is a representative sample of the population.

### Rank-Based Threshold Selection

Sort the $M$ distances in ascending order:

$$s_{(1)} \leq s_{(2)} \leq \cdots \leq s_{(M)}.$$

These are the *order statistics* of the impostor distance sample. The $k$-th order statistic $s_{(k)}$ defines the *$k$-th error pair threshold*:

$$\tau_k = s_{(k)}.$$

At this threshold, exactly $k$ of the $M$ impostor pairs fall at or below $\tau_k$ and would be falsely accepted. The realized false acceptance rate is

$$\text{FAR}(k) = \frac{k}{M}.$$

This gives the inverse of the empirical CDF:

$$\tau_k = \hat{F}_n^{-1}\!\left(\frac{k}{M}\right).$$

### Design Operating Point

For a target FAR of $\alpha$ (e.g., $\alpha = 10^{-4}$ for 100 ppm), the required error-pair rank is

$$k^* = \lceil \alpha M \rceil.$$

The threshold is $\tau_{k^*} = s_{(k^*)}$. This produces a realized FAR of $k^* / M$, the finest resolution the gallery supports.

**Spec anchor points**:

| Dataset | $n$ | $M$ | Target FAR | $k^*$ | Realized FAR |
|---------|-----|-----|------------|-------|-------------|
| La Salle DB1 | 28 | 756 | 10,000 ppm (1%) | 8 | 10,582 ppm |
| LFW DB1 | 5,749 | ~33M | 10 ppm | 331 | ~10 ppm |

The La Salle DB1's $M=756$ cannot resolve finer than $\approx 1/M \approx 1\,300$ ppm, which is why the 100 ppm budget is certified on LFW rather than the local gallery.

## 3. The Sequential Probability Integral Transform Interpretation

Order statistics admit a well-known distributional result. If the $s_{ij}$ are independent draws from a continuous CDF $F$, then the probability integral transform $U_{ij} = F(s_{ij})$ yields $M$ i.i.d. $\text{Uniform}(0,1)$ variables. The $k$-th order statistic of $U$ follows a $\text{Beta}(k, M-k+1)$ distribution with

$$\mathbb{E}[U_{(k)}] = \frac{k}{M+1}, \qquad \text{Var}[U_{(k)}] = \frac{k(M-k+1)}{(M+1)^2(M+2)}.$$

This provides exact finite-sample inference: a $(1-\gamma)$ confidence band around $s_{(k)}$ is

$$F^{-1}\!\left(q_{\gamma/2}\right) \leq s_{(k)} \leq F^{-1}\!\left(q_{1-\gamma/2}\right)$$

where $q_p$ is the $p$-th quantile of $\text{Beta}(k, M-k+1)$.

In practice, $F$ is unknown, so we bootstrap confidence intervals by resampling the gallery (Section 5).

## 4. Connection to Extrema and Rare-Event Estimation

The smallest order statistic $s_{(1)}$ is the minimum impostor distance. For a recognizer with good identity separation, $s_{(1)}$ is the critical value - the closest any two different people appear to the algorithm. The distribution of $s_{(1)}$ follows a minimum extreme-value distribution:

$$\Pr(s_{(1)} \leq t) = 1 - [1 - F(t)]^M.$$

As $M$ grows, $s_{(1)}$ concentrates near the lower tail of $F$. This explains why increasing $M$ (using LFW instead of La Salle) necessarily surfaces more near-zero-distance pairs: the extreme-value distribution shifts left with sample size, making rare lookalike pairs inevitable.

This also explains the annotation-error detection property: if $s_{(1)} \approx 0$ for a genuine impostor pair, either:
- The two images are of the same person mislabeled (annotation error), or
- The recognizer's feature space has collapsed (algorithmic failure).

Both causes are surfaced by the same extreme-value argument.

## 5. Bootstrap Confidence Intervals

For a given $k$, the threshold $\tau_k = s_{(k)}$ is a point estimate. To quantify uncertainty, bootstrap the gallery:

1. Draw $B$ bootstrap samples of $n$ identities (with replacement) from the original $n$.
2. For each bootstrap sample $b$, compute the $k$-th error pair threshold $\tau_k^{(b)}$.
3. The $(\alpha/2, 1-\alpha/2)$ percentiles of $\{\tau_k^{(b)}\}$ give a $(1-\alpha)$ confidence interval for $\tau_k$.

The confidence interval width depends on $n$ and the tail behavior of $F$. For $n=28$ (La Salle), intervals are wide; for $n=5\,749$ (LFW), they tighten considerably.

## 6. Why Exhaustive Comparison Beats Sampled Pairs

Standard face verification protocols (e.g., the LFW 10-fold protocol) fix a set of 3,000 genuine and 3,000 impostor pairs. This sampled-pair approach has two limitations:

| Property | Sampled Pairs (LFW protocol) | Exhaustive (Independence Test) |
|----------|------------------------------|-------------------------------|
| FAR resolution | $\approx 1/3\,000 \approx 333$ ppm | $1/M = 1/(n(n-1))$, as fine as 0.03 ppm for $n=5\,749$ |
| Empirical CDF | 3,000 point estimates | $M$ point estimates spanning the full tail |
| Annotation error detection | Missed unless the pair is sampled | Guaranteed: smallest distances are observed |
| Model comparison | AUC over fixed pair set | Direct comparison of order statistics |

The exhaustive approach reveals the *full tail* of the impostor distribution, not just a $3\,000$-point sample. This is critical for low-FAR operation (100 ppm or lower), where the sampling error of a 3,000-pair set is an order of magnitude larger than the effect being measured.

## 7. Application to Model Selection

Given $R$ candidate recognizers, each with impostor order statistics $s_{(k)}^{(r)}$, the ranking criterion at target FAR $\alpha$ is:

$$r^* = \arg\max_r s_{(k^*)}^{(r)} \quad \text{where } k^* = \lceil \alpha M \rceil.$$

The recognizer whose $k^*$-th error pair threshold is *highest* has the widest margin at the target FAR. This directly answers the question: "Which recognizer can maintain the lowest FAR while still accepting genuine users?"

On La Salle DB1 ($n=28$, $M=756$, $k^* = 8$):

| Recognizer | $\tau_8$ (raw) | $\tau_8$ (normalized) |
|-----------|----------------|----------------------|
| LBPH (Tan-Triggs) | 21.35 | 85.88 |
| Eigenfaces | 8,098.46 | 71.00 |
| Fisherfaces | 5,446.46 | 66.38 |

LBPH achieves the highest normalized threshold - the widest impostor margin - and is the only recognizer that can hold the 100 ppm budget on LFW.

## 8. Threshold Propagation to Deployment

Once $\tau_{k^*}$ is fixed by independence testing, it becomes the *deployable threshold* for the verifier. The recognition pipeline then operates as:

$$\text{Decision}(x_{\text{probe}}, I_i) = \begin{cases}
\text{Accept} & \text{if } \delta(f(x_{\text{probe}}), g_i) \leq \tau_{k^*}, \\
\text{Reject} & \text{otherwise},
\end{cases}$$

where $g_i$ is the gallery template for identity $I_i$.

This is the mechanism by which the independence test drives the hybrid cascade: the gate's `tau_accept` (73.04 normalized) and `tau_reject` (76.85 normalized) are thresholds derived from the LBPH-LFW independence run at 100 ppm FAR.

## References

[1] H. A. David and H. N. Nagaraja, *Order Statistics*, 3rd ed. Hoboken, NJ: Wiley, 2003.
[2] ISO/IEC 19795-1:2006, "Information Technology - Biometric Performance Testing and Reporting - Part 1: Principles and Framework," 2006.
[3] G. B. Huang, M. Ramesh, T. Berg, and E. Learned-Miller, "Labeled Faces in the Wild: A Database for Studying Face Recognition in Unconstrained Environments," Univ. Massachusetts, Amherst, Tech. Rep. 07-49, 2007.
