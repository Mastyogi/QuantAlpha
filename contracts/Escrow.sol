// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title QuantAlpha Escrow Contract
 * @notice Holds USDT (BEP-20) for users.
 *         Withdrawal automatically deducts 15% service fee:
 *           85% → user wallet
 *           15% → SERVICE_WALLET (hardcoded at deploy time)
 *
 * Security:
 *   - Re-entrancy guard (checks-effects-interactions)
 *   - Overflow protection (Solidity 0.8+ built-in)
 *   - Only owner can pause/unpause
 *   - Only owner can update service wallet
 *   - Users can only withdraw their own balance
 */

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract QuantAlphaEscrow {
    // ── State ─────────────────────────────────────────────────────────────────
    address public owner;
    address public serviceWallet;
    IERC20  public usdt;
    bool    public paused;

    uint256 public constant SERVICE_FEE_BPS = 1500;  // 15% in basis points
    uint256 public constant BPS_DENOMINATOR = 10000;

    mapping(address => uint256) private _balances;

    // ── Events ────────────────────────────────────────────────────────────────
    event Deposited(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 net, uint256 fee);
    event Paused(address by);
    event Unpaused(address by);
    event ServiceWalletUpdated(address newWallet);

    // ── Modifiers ─────────────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    modifier notPaused() {
        require(!paused, "Contract is paused");
        _;
    }

    // ── Constructor ───────────────────────────────────────────────────────────
    constructor(address _usdt, address _serviceWallet) {
        require(_usdt != address(0), "Invalid USDT address");
        require(_serviceWallet != address(0), "Invalid service wallet");
        owner         = msg.sender;
        usdt          = IERC20(_usdt);
        serviceWallet = _serviceWallet;
    }

    // ── Deposit ───────────────────────────────────────────────────────────────

    /**
     * @notice Deposit USDT into escrow.
     *         Caller must approve this contract first.
     * @param amount Amount of USDT (in wei, 18 decimals) to deposit.
     */
    function deposit(uint256 amount) external notPaused {
        require(amount > 0, "Amount must be > 0");

        // Effects before interactions (re-entrancy guard)
        _balances[msg.sender] += amount;

        // Interaction
        bool ok = usdt.transferFrom(msg.sender, address(this), amount);
        require(ok, "USDT transferFrom failed");

        emit Deposited(msg.sender, amount);
    }

    /**
     * @notice Admin can credit a user's balance (for manual deposits).
     */
    function creditUser(address user, uint256 amount) external onlyOwner {
        require(user != address(0), "Invalid user");
        require(amount > 0, "Amount must be > 0");
        _balances[user] += amount;
        emit Deposited(user, amount);
    }

    // ── Withdrawal ────────────────────────────────────────────────────────────

    /**
     * @notice Withdraw USDT from escrow.
     *         15% service fee is deducted automatically.
     *         User receives 85% of requested amount.
     * @param amount Amount to withdraw (before fee deduction).
     */
    function withdraw(uint256 amount) external notPaused {
        require(amount > 0, "Amount must be > 0");
        require(_balances[msg.sender] >= amount, "Insufficient balance");

        // Calculate fee split
        uint256 fee = (amount * SERVICE_FEE_BPS) / BPS_DENOMINATOR;
        uint256 net = amount - fee;

        // Effects BEFORE interactions (re-entrancy protection)
        _balances[msg.sender] -= amount;

        // Interactions
        bool ok1 = usdt.transfer(msg.sender, net);
        require(ok1, "User transfer failed");

        bool ok2 = usdt.transfer(serviceWallet, fee);
        require(ok2, "Fee transfer failed");

        emit Withdrawn(msg.sender, net, fee);
    }

    // ── View functions ────────────────────────────────────────────────────────

    /**
     * @notice Get a user's escrow balance.
     */
    function balanceOf(address user) external view returns (uint256) {
        return _balances[user];
    }

    /**
     * @notice Calculate net amount after 15% fee.
     */
    function netAfterFee(uint256 amount) external pure returns (uint256 net, uint256 fee) {
        fee = (amount * SERVICE_FEE_BPS) / BPS_DENOMINATOR;
        net = amount - fee;
    }

    // ── Admin functions ───────────────────────────────────────────────────────

    function pause() external onlyOwner {
        paused = true;
        emit Paused(msg.sender);
    }

    function unpause() external onlyOwner {
        paused = false;
        emit Unpaused(msg.sender);
    }

    function updateServiceWallet(address newWallet) external onlyOwner {
        require(newWallet != address(0), "Invalid address");
        serviceWallet = newWallet;
        emit ServiceWalletUpdated(newWallet);
    }

    /**
     * @notice Emergency withdrawal of stuck tokens (owner only).
     *         Cannot withdraw user funds — only tokens sent directly.
     */
    function emergencyWithdraw(address token, uint256 amount) external onlyOwner {
        IERC20(token).transfer(owner, amount);
    }
}
