# ======================================================================================================================
# Implementing oerlemans's 2005 paper
# ======================================================================================================================

# ======================================================================================================================
# Steps:
# 1. Calculate the Known Values and Functions:
#     1.1 calculate c and tau
#     1.2 Get L_prime_t
#
# 2. Calculate length change derivative: dL'(t)/dt. Rate of change of glacier length over time
#     2.1 Forward, Backward, central?
#     2.2 dL'(t_i) / dt = (L'(t_i+1) - L'(t_i)) / ((t_i+1) - (t_i))
#
# 3. Calculate (-1/c)*L'(t)
# 4. Calculate (-1/c) * tau * (dL'(t)/dt)
# 5. Get temp change at time t. Sum 3 and 4.
# ======================================================================================================================

import matplotlib.pyplot as plt

# ======================================================================================================================
# ======================================================================================================================
# STEP 1.

# Define change in gacier length for each year.
# This would be the CHANGE and not the overall length.
# positive = increase, negative = decrease
# TODO: Find out how this data was obtained.
L_prime_t = [-0.2, -0.25, -0.3, -0.35, -0.4, -0.42, -0.43, -0.44, -0.45, -0.46, -0.47]  # Dummy data at the moment.

# Define time period. del_t = time_n+1 - time_n
time = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]  # Dummy data at the moment.

# TODO: Look into -> Probably define 'L_prime_t' and 'time' as a key value pair (dict)? more clearer?
#       Also 'tau' function of 'Length'. Ref. length had to be known. How is glacier length known?
#       People measured? In 1600?
#       Details in page 61-73 and 83-92 in book. ISBN: 9789026518133
#       Find this book [T.U central library] ->  J. Oerlemans, Glaciers and Climate Change ISBN: 9789026518133


# Define constants? 'c' and tau.
# Why are these constants? 'c' depends on slope.
# slope could change with time? Also, precipitation would be different?
# 'c' and 'tau'. Find out exactly how he got the formula.
# tau is response time, meaning this is the time taken by glacier to be in equilibrium after temp/precip change.

# beta = altitudinal mass-balance gradient

def calculate_c(p, s):
    # This is climate sensitivity defined as: c = 2.3 * P ^ (0.6) * (s ^ (–1))
    # P = climatological annual precip. s = mean slope
    # TODO: 'climatological' meaning averaged? If so, 30 years? how long? precip. = only snow or total?
    #
    c = []
    if len(p) == len(s) == 1:
        c.append(2.3 * p[0] ** 0.6 * s[0] ** (-1))
        return c
    else:
        for i, j in zip(p, s):
            c.append(2.3 * p ** 0.6 * s ** (-1))
        return c


def calculate_tau(beta, s, l):
    # tau = 13.6 * beta ^ (–1) * s ^ (–1) * (1 + 20 * s) ^ (–1/2) * L ^ (–1/2)
    # tau = Response time -> given change in temp,precip how long till equilibrium?
    tau = []
    if len(beta) == len(s) == len(l) == 1:
        tau.append(13.6 * beta[0] ** (-1) * s[0] ** (-1) * (1 + 20 * s[0]) ** (-1/2) * l[0] ** (-1/2))
        return tau
    else:
        for i, j, k in zip(beta, s, l):
            tau.append(13.6 * beta ** (-1) * s ** (-1) * (1 + 20 * s) ** (-1/2) * l ** (-1/2))
        return tau


def calculate_beta(p):
    # m.w.e / altitude? empirical? Read book.
    return [.006 * p[0] ** (1/2)]


p = [1]  # meters / year.
s = [20]  # Mean slope. In degrees? Radians? TODO: Find out. Match dimensions in eqn. If empirical -> maynot
# Reference length. At 1950.
# TODO: Implement a list of glacier length for all years as a dict?. dL'(t)/dt would then be clearer.
l = [10000]  # In meters

c = calculate_c(p,s)
beta = calculate_beta(p)
tau = calculate_tau(beta, s, l)

# ======================================================================================================================
# ======================================================================================================================


# ======================================================================================================================
# ======================================================================================================================
# STEP 2

# calculate derivative dL'(t) / dt. Forward method.
# TODO: Do central. Implement linear interpolation.

def calculate_derivative(time, data):
    dL_prime_dt = []
    for i in range(len(time) - 1):
        dt = time[i + 1] - time[i]
        dL_prime = data[i + 1] - data[i]
        dL_prime_dt.append(dL_prime / dt)
    return dL_prime_dt


# Compute dL'(t)/dt
dL_prime_dt = calculate_derivative(time, L_prime_t)

# ======================================================================================================================
# ======================================================================================================================


# ======================================================================================================================
# ======================================================================================================================
# STEP 3
# Calculate the term -1/c * L'(t)
L_term = [- (1 / c[0]) * L for L in L_prime_t]
del L_term[-1]
print(L_term)
print(len(L_term))
# ======================================================================================================================
# ======================================================================================================================


# ======================================================================================================================
# ======================================================================================================================
# STEP 4

# Calculate (1/c) * tau * (dL'(t)/dt)
rate_of_change_term = [(1 / c[0]) * tau[0] * d for d in dL_prime_dt]

print(rate_of_change_term)
print(len(rate_of_change_term))

# ======================================================================================================================
# ======================================================================================================================


# ======================================================================================================================
# ======================================================================================================================
# STEP 5

# Compute the temperature T'(t).
# TODO: this does not work as is. things are not of the same length?. Rectify. Probably add or remove last data?
#       Central method fixes this? Look into.
#
# Temporary fix
# del L_term[-1]
# print(L_term)
# print(len(L_term))
del time[-1]

T_prime = [L_term[i] + rate_of_change_term[i] for i in range(len(time))]
print(T_prime)

# ======================================================================================================================
# ======================================================================================================================

# Plot stuffs
# TODO: RECHECK ALL FORMULAS. PLOTS NOT AS EXPECTED.
# Plotting the results
plt.figure(figsize=(12, 8))
plt.plot(time, T_prime, label="T'(t) (Temperature Perturbation)", color='r', linewidth=2)
plt.plot(time[:], L_term, label="-1/c * L'(t)", color='b', linestyle='--', marker='o')
plt.scatter(time[:-1], rate_of_change_term[:-1], label="(1/c) * tau * dL'/dt", color='g', marker='x')
plt.xlabel('Time (years)')
plt.ylabel('Perturbation')
plt.title("Temperature Perturbation T'(t) vs Time")
plt.legend()
plt.grid(True)
plt.show()