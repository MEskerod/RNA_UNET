import numpy as np

####### HELP FUNCTIONS #######

def declare_global_variable(seq, M) -> None: 
    """
    Declares the global variables used troughout all the other functions. 

    Args: 
        - b_stacking: Is stacking retained for bulge loops of size 1 [True/False] (default = False)
        - closing: Is closing penalty added for GU/UG and AU/UA base pairs that closses interior loops [True/False] (default = False)
        - asymmetry: Is a penalty added for asymmetric interior loops [True/False] (default = False)
    """
    global basepairs, sequence, matrix

    basepairs = {'AU', 'UA', 'CG', 'GC', 'GU', 'UG'}
    sequence = seq
    matrix = M


### LOOP ENERGIES ###
def find_E1(i: int, j: int) -> float:
    """
    E1 are the energy of base pairing between Si and Sj with one internal edge (hairpin loop) 
    """
    
    energy = matrix[i, j]

    return energy

def find_E2(i: int, j: int, V: np.ndarray) -> float: 
    """
    E2 is the energy of basepairing between i and j and i' and j' resulting in two internal edges (stacking, bulge loop or internal loop)
    i<i'<j'<j
    Returns the minimum of the 3 options  
    """  
    energy = float('inf')
    ij = None

    for ip in range(i+1, j-2): 
        for jp in range(ip+3, j): 
            if (sequence[ip] + sequence[jp]) in basepairs:
                energy_loop = matrix[i, j] + V[ip, jp]
                if energy_loop < energy: 
                    energy = energy_loop
                    ij = (ip, jp) 
    return energy, ij

def find_E3(i: int, j: int, W: np.array) -> float: 
    """
    E3 is the energy of a structure that contains more than two internal edges (bifurcating loop)
    The energy is the energy of the sum of the substructures 
    i+1<i'<j-2
    """
    energy = float('inf')
    ij = None

    #Try all combinations of substructure and save the one that gives the lowest energy
    for ip in range(i+2, j-2):  
        loop_energy = W[i+1, ip] + W[ip+1, j-1]
        if loop_energy < energy: 
            energy = round(loop_energy, 5)
            ij = (ip, ip+1)
    return energy, ij

def find_E4(i: int, j: int, W: np.array) -> tuple[float, tuple[int, int]]: 
    """
    E4 is the energy when i and j are both in base pairs, but not with each other. 
    It find the minimum of combinations of two possible subsequences containing i and j
    """
    energy = float('inf')
    ij = None

    for ip in range(i+1, j-1): 
        subsequence_energy = W[i, ip] + W[ip+1, j]
        
        if subsequence_energy < energy: 
            energy = round(subsequence_energy, 5)
            ij = (ip, ip+1)

    return energy, ij

def penta_nucleotides(W: np.array, V: np.array) -> None:
    """
    Fills out the first entries in the matrices V and W 
    The shortest possible subsequences are of length 5 and can only form hairpin loops of size 3 if i and j basepair
    """
    N = len(sequence)

    for i in range(0, N-4): 
        j = i+4
        bp = sequence[i]+sequence[j]
        if bp not in basepairs:
            V[i,j] = W[i,j ]= float('inf')
        else: 
            V[i,j] = W[i,j] = matrix[i, j] 

### FILL V AND W ###
def compute_V(i: int, j: int, W: np.array, V: np.array) -> None: 
    """
    Computes the minimization over E1, E2 and E3, which will give the value at V[i,j]
    """

    if sequence[i] + sequence[j] in basepairs:
        v = min(find_E1(i, j), 
                find_E2(i, j, V)[0], 
                find_E3(i, j, W)[0])

    else: 
        v = float('inf')

    V[i, j] = v

def compute_W(i: int, j: int, W: np.array, V: np.array) -> None:
    """
    Computes the minimization over possibilities for W and fills out the entry at W[i,j]
     Possibilities are: 
    - i or j in a structure (W[i+1, j] or W[i, j-1])
    - i and j basepair with each other (V[i,j])
    - i and j both base pair but not with each other (E4)
    """
    w = min(W[i+1,j], W[i,j-1], V[i,j], find_E4(i, j, W)[0])

    W[i,j] = w


def fold_rna() -> tuple[np.array, np.array]: 
    """
    Fills out the W and V matrices to find the fold that gives the minimum free energy
    Follows Mfold as desribed by M. Zuker

    The V matrix contains the minimum free energy for the subsequences i and j, if i and j has to form a pair. 
    If i and j are not able to basepair the energy will be infinity (not a possible structure)

    The W matrix contains the minimum free energy for the subsequences i and j where base pairing between i and j is not nessecary.
    """
    N = len(sequence)
    W, V = np.full([N, N], float('inf')), np.full([N, N], float('inf'))


    #Fills out the table with all posible penta nucleotide subsequences
    # Penta nucleotides are the base cases. If subsequences are shorter they cannot be folded
    penta_nucleotides(W, V) 

    for l in range(5, N): #Computes the best score for all subsequences that are longer than 5 nucleotides with increasing length
        for i in range(0, N-5): 
            j = i+l
            if j < N: 
                compute_V(i, j, W, V) 
                compute_W(i, j, W, V)

    return W, V

def find_optimal(W: np.array) -> float: 
    """
    Find the final energy of the folded RNA
    """
    return W[0, -1]

### BACTRACKING ### 

def backtrack(W: np.array, V: np.array) -> str: 
    """
    Backtracks trough the W, V matrices to find the final fold
    Returns the fold as a dotbracket structure
    """
    pairs = []

    N = W.shape[0]-1
    
    j = W.shape[0]-1
    i = 0

    def trace_V(i: int, j: int) -> None: 
        """
        Traces backwards trough the V matrix recursively to find the secondary structure
        """
        if V[i,j] == find_E1(i, j): 
            pairs.append((i, j))
        
        elif V[i,j] == find_E2(i, j, V)[0]:
            ij = find_E2(i, j, V)[1]
            pairs.append((i, j))
            trace_V(ij[0], ij[1])
    
        elif V[i, j] == find_E3(i, j, W)[0]: 
            ij = find_E3(i, j, W)[1]
            pairs.append((i, j))
            trace_W(i+1, ij[0]), trace_W(ij[1], j-1)

    def trace_W(i: int, j: int) -> None: 
        """
        Traces backwards trough the W matrix recursively to find the secondary structure
        """
        if i < N and W[i,j] == W[i+1, j]: 
            trace_W(i+1, j)

        elif j > 0 and W[i,j] == W[i, j-1]: 
            trace_W(i, j-1)

        elif W[i, j] == V[i, j]: 
            trace_V(i, j)

        elif W[i,j] == find_E4(i, j, W)[0]: 
            ij = find_E4(i,j,W)[1] 
            trace_W(i, ij[0]), trace_W(ij[1], j)
    
    #Fill out db
    trace_W(i, j)

    return pairs


def Mfold(sequence: str, matrix: np.array): 
    """
    """
    declare_global_variable(sequence, matrix)

    W, V = fold_rna()
    fold = backtrack(W, V)

    return fold



sequence = 'CGUGUCAGGUCCGGAAGGAAGCAGCACUAAC'
pairs = [0, 26, 25, 24, 23, 0, 0, 0, 0, 18, 17, 16, 0, 0, 0, 0, 11, 10, 9, 0, 0, 0, 0, 4, 3, 2, 1, 0, 0, 0, 0]

matrix = np.zeros((len(pairs), len(pairs)))
for i in range(len(pairs)):
    if pairs[i] != 0:
        matrix[i, pairs[i]] = -1
    else: 
        matrix[i, i] = -1

print(Mfold(sequence, matrix))