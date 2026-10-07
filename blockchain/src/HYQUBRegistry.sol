// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract HYQUBRegistry {

    struct SecurityProfile {
        bytes32 keyHash;
        uint256 keyVersion;
        bool registered;
    }

    mapping(address => SecurityProfile) public profiles;

    address public immutable registrar;

    event WalletRegistered(
        address indexed wallet,
        bytes32 keyHash
    );

    event KeyRotated(
        address indexed wallet,
        bytes32 newKeyHash,
        uint256 newKeyVersion
    );

    constructor() {
        registrar = msg.sender;
    }

    modifier onlyRegistrar() {
        require(msg.sender == registrar, "Not authorized");
        _;
    }

    function registerWallet(
        address _wallet,
        bytes32 _keyHash
    ) external onlyRegistrar {
        require(!profiles[_wallet].registered, "Already registered");

        profiles[_wallet] = SecurityProfile({
            keyHash: _keyHash,
            keyVersion: 1,
            registered: true
        });

        emit WalletRegistered(_wallet, _keyHash);
    }

    function rotateKey(
        address _wallet,
        bytes32 _newKeyHash
    ) external onlyRegistrar {
        require(profiles[_wallet].registered, "Not registered");

        SecurityProfile storage profile = profiles[_wallet];

        profile.keyHash = _newKeyHash;
        profile.keyVersion += 1;

        emit KeyRotated(
            _wallet,
            _newKeyHash,
            profile.keyVersion
        );
    }

    function isRegistered(
        address _wallet
    ) external view returns (bool) {
        return profiles[_wallet].registered;
    }

    function getKeyHash(
        address _wallet
    ) external view returns (bytes32) {
        require(
            profiles[_wallet].registered,
            "Not registered"
        );

        return profiles[_wallet].keyHash;
    }

    function getKeyVersion(
        address _wallet
    ) external view returns (uint256) {
        require(
            profiles[_wallet].registered,
            "Not registered"
        );

        return profiles[_wallet].keyVersion;
    }
}
